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
    """Detect the system's IANA timezone name (e.g. 'America/Los_Angeles').
    Falls back to 'UTC' if detection fails."""
    try:
        link = pathlib.Path('/etc/localtime').resolve()
        parts = str(link).split('zoneinfo/')
        if len(parts) > 1:
            return parts[1]
    except Exception:
        pass
    return 'UTC'


class DatabaseConfig:
    """Configuration loader for database settings."""
    
    _instance: Optional['DatabaseConfig'] = None
    
    def __init__(self, config_path: str = None):
        # Load from settings.yaml as defaults
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), 
                '..', '..', 'config', 'settings.yaml'
            )
        
        # Check for environment variables first (Docker)
        self.host = os.environ.get('DB_HOST', 'localhost')
        self.port = int(os.environ.get('DB_PORT', '5432'))
        self.name = os.environ.get('DB_NAME', 'openbrain')
        self.user = os.environ.get('DB_USER', 'postgres')
        self.password = os.environ.get('DB_PASSWORD', '')
        self.timezone = os.environ.get('DB_TIMEZONE', 'auto')

        # If no env vars, try loading from config file
        if self.host == 'localhost' and not self.password:
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                self.host = config['database'].get('host', 'localhost')
                self.port = config['database'].get('port', 5432)
                self.name = config['database'].get('name', 'openbrain')
                self.user = config['database'].get('user', 'postgres')
                self.password = config['database'].get('password', '')
                self.timezone = config['database'].get('timezone', 'auto')
            except Exception:
                pass

        if self.timezone == 'auto':
            self.timezone = _detect_local_timezone()
    
    @classmethod
    def get_instance(cls, config_path: str = None) -> 'DatabaseConfig':
        if cls._instance is None:
            cls._instance = cls(config_path)
        return cls._instance


class ConnectionPool:
    """PostgreSQL connection pool manager."""
    
    _pool: Optional[pool.ThreadedConnectionPool] = None
    
    def __init__(self, minconn: int = 1, maxconn: int = 10):
        self.minconn = minconn
        self.maxconn = maxconn
    
    def initialize(self) -> None:
        """Initialize the connection pool."""
        if self._pool is None:
            config = DatabaseConfig.get_instance()
            self._pool = pool.ThreadedConnectionPool(
                self.minconn,
                self.maxconn,
                host=config.host,
                port=config.port,
                database=config.name,
                user=config.user,
                password=config.password,
                options=f"-c timezone={config.timezone}"
            )
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool."""
        if self._pool is None:
            self.initialize()

        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
        finally:
            if conn is not None:
                self._pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, dict_cursor: bool = True):
        """Get a cursor from the pool."""
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


# Global connection pool instance
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
