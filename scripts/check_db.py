#!/usr/bin/env python3
"""Check if database needs setup."""

import os
import sys
import psycopg2

def check_db():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'postgres'),
            port=int(os.getenv('DB_PORT', '5432')),
            database=os.getenv('DB_NAME', 'openbrain'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'openbrain')
        )
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM memory LIMIT 1")
        conn.close()
        return 0  # Database is ready
    except Exception as e:
        if "relation" in str(e) and "does not exist" in str(e):
            return 1  # Needs setup
        print(f"Error: {e}")
        return 2  # Other error

if __name__ == "__main__":
    sys.exit(check_db())
