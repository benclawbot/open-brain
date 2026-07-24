#!/usr/bin/env python3
"""
Database setup script for Open Brain.
Initializes the PostgreSQL database with pgvector.
"""
import os
import sys

import psycopg2
import yaml


def load_config():
    """Load configuration from settings.yaml."""
    config_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'config', 'settings.yaml'
    )
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_connection(config, database=None):
    """Get a database connection.

    Environment variables override config file values so that docker-compose
    and other container runtimes can inject the runtime host/port without
    editing config/settings.yaml.
    """
    db = config['database']
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', db['host']),
        port=int(os.environ.get('DB_PORT', db['port'])),
        database=database or os.environ.get('DB_NAME', db['name']),
        user=os.environ.get('DB_USER', db['user']),
        password=os.environ.get('DB_PASSWORD', db.get('password', ''))
    )


def create_database(config):
    """Create the database if it doesn't exist."""
    # Connect to default postgres database
    conn = get_connection(config, database='postgres')
    conn.autocommit = True
    cursor = conn.cursor()
    
    db_name = config['database']['name']
    
    # Check if database exists
    cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
    exists = cursor.fetchone()
    
    if not exists:
        print(f"Creating database: {db_name}")
        cursor.execute(f"CREATE DATABASE {db_name}")
        print(f"Database {db_name} created successfully")
    else:
        print(f"Database {db_name} already exists")
    
    cursor.close()
    conn.close()


def enable_extensions(config):
    """Enable required PostgreSQL extensions."""
    conn = get_connection(config)
    cursor = conn.cursor()
    
    # Enable uuid-ossp
    cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    print("Enabled: uuid-ossp")
    
    # Enable vector extension
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS \"vector\"")
        print("Enabled: vector")
    except psycopg2.Error as e:
        print(f"Warning: Could not enable vector extension: {e}")
        print("Make sure pgvector is installed: CREATE EXTENSION vector")
    
    conn.commit()
    cursor.close()
    conn.close()


def create_schema(config):
    """Create database schema."""
    schema_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'src', 'db', 'schema.sql'
    )
    
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    conn = get_connection(config)
    cursor = conn.cursor()
    
    # Execute schema
    cursor.execute(schema_sql)
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("Schema created successfully")


def verify_setup(config):
    """Verify the database setup."""
    conn = get_connection(config)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"\nTables created: {', '.join(tables)}")
    
    # Check indexes
    cursor.execute("""
        SELECT indexname 
        FROM pg_indexes 
        WHERE schemaname = 'public'
    """)
    indexes = [row[0] for row in cursor.fetchall()]
    
    print(f"Indexes created: {len(indexes)}")
    
    cursor.close()
    conn.close()
    
    return 'memory' in tables


def main():
    """Main setup function."""
    print("=" * 50)
    print("Open Brain Database Setup")
    print("=" * 50)
    
    # Load config
    config = load_config()
    
    # Check DB_PASSWORD
    db_password = os.environ.get('DB_PASSWORD', config['database'].get('password', ''))
    if not db_password:
        print("\nERROR: DB_PASSWORD environment variable not set")
        print("Set it with: export DB_PASSWORD=your_password")
        sys.exit(1)
    
    try:
        # Create database
        print("\n[1/4] Creating database...")
        create_database(config)
        
        # Enable extensions
        print("\n[2/4] Enabling extensions...")
        enable_extensions(config)
        
        # Create schema
        print("\n[3/4] Creating schema...")
        create_schema(config)
        
        # Verify
        print("\n[4/4] Verifying setup...")
        if verify_setup(config):
            print("\n✓ Database setup complete!")
        else:
            print("\n✗ Setup verification failed")
            sys.exit(1)
    
    except psycopg2.OperationalError as e:
        print(f"\nERROR: Could not connect to database: {e}")
        print("\nMake sure PostgreSQL is running and accessible.")
        sys.exit(1)
    
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
