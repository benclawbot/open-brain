"""
Database connection management for Open Brain.
"""
import os
import pathlib
from contextlib import contextmanager
from typing import Optional

import yaml
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor


def _detect_local_timezone() -> str:
    """Detect the system's IANA timezone name; fall back to UTC."""
    try:
        link = pathlib.Path("/etc/localtime").resolve()
        parts = str(link).split("zoneinfo/")
        if len(parts) > 1:
            return parts[1]
    except Exception:
        pass
    return "UTC"


def _positive_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be at least 1")
    return value


class DatabaseConfig:
    """Configuration loader for database and pool settings."""

    _instance: Optional["DatabaseConfig"] = None

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "config", "settings.yaml"
            )

        self.host = os.environ.get("DB_HOST", "localhost")
        self.port = int(os.environ.get("DB_PORT", "5432"))
        self.name = os.environ.get("DB_NAME", "openbrain")
        self.user = os.environ.get("DB_USER", "postgres")
        self.password = os.environ.get("DB_PASSWORD", "")
        self.timezone = os.environ.get("DB_TIMEZONE", "auto")
        self.pool_min = _positive_int_env("DB_POOL_MIN", 1)
        self.pool_max = _positive_int_env("DB_POOL_MAX", 10)
        self.connect_timeout = _positive_int_env("DB_CONNECT_TIMEOUT", 5)

        if self.pool_min > self.pool_max:
            raise ValueError("DB_POOL_MIN cannot exceed DB_POOL_MAX")

        if self.host == "localhost" and not self.password:
            try:
                with open(config_path, "r", encoding="utf-8") as config_file:
                    config = yaml.safe_load(config_file) or {}
                database = config.get("database", {})
                self.host = database.get("host", "localhost")
                self.port = database.get("port", 5432)
                self.name = database.get("name", "openbrain")
                self.user = database.get("user", "postgres")
                self.password = database.get("password", "")
                self.timezone = database.get("timezone", "auto")
            except (OSError, TypeError, KeyError, yaml.YAMLError):
                pass

        if self.timezone == "auto":
            self.timezone = _detect_local_timezone()

    @classmethod
    def get_instance(cls, config_path: str = None) -> "DatabaseConfig":
        if cls._instance is None:
            cls._instance = cls(config_path)
        return cls._instance


class ConnectionPool:
    """Thread-safe PostgreSQL connection pool manager."""

    _pool: Optional[pool.ThreadedConnectionPool] = None

    def __init__(self, minconn: int | None = None, maxconn: int | None = None):
        self.minconn = minconn
        self.maxconn = maxconn

    def initialize(self) -> None:
        """Initialize the connection pool once."""
        if self._pool is None:
            config = DatabaseConfig.get_instance()
            minconn = self.minconn if self.minconn is not None else config.pool_min
            maxconn = self.maxconn if self.maxconn is not None else config.pool_max
            if minconn < 1 or maxconn < minconn:
                raise ValueError("invalid database pool bounds")
            self._pool = pool.ThreadedConnectionPool(
                minconn,
                maxconn,
                host=config.host,
                port=config.port,
                database=config.name,
                user=config.user,
                password=config.password,
                connect_timeout=config.connect_timeout,
                application_name="openbrain",
                options=f"-c timezone={config.timezone}",
            )

    @contextmanager
    def get_connection(self):
        """Get a connection and discard it if it becomes unusable."""
        if self._pool is None:
            self.initialize()

        conn = None
        discard = False
        try:
            conn = self._pool.getconn()
            if conn.closed:
                discard = True
                raise psycopg2.InterfaceError("database pool returned a closed connection")
            yield conn
        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            discard = True
            raise
        finally:
            if conn is not None:
                self._pool.putconn(conn, close=discard or bool(conn.closed))

    @contextmanager
    def get_cursor(self, dict_cursor: bool = True):
        """Get a transactional cursor with commit/rollback guarantees."""
        with self.get_connection() as conn:
            cursor = conn.cursor(
                cursor_factory=RealDictCursor if dict_cursor else None
            )
            try:
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()

    def close_all(self) -> None:
        """Close all connections in the pool."""
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None


_pool = ConnectionPool()


def get_pool() -> ConnectionPool:
    """Get the global connection pool."""
    return _pool


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    with _pool.get_connection() as conn:
        yield conn


@contextmanager
def get_db_cursor(dict_cursor: bool = True):
    """Context manager for database cursors."""
    with _pool.get_cursor(dict_cursor) as cursor:
        yield cursor


def init_db(config_path: str = None) -> None:
    """Initialize the database connection pool."""
    if config_path:
        DatabaseConfig._instance = None
        DatabaseConfig.get_instance(config_path)
    _pool.initialize()
