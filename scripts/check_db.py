#!/usr/bin/env python3
"""Simple DB smoke-check for the MCBI portal.

Attempts to connect to the DATABASE_URL environment variable using psycopg2
with a short timeout. Exits with 0 on success, 1 on failure and prints a
user-friendly message.
"""
import os
import sys
import psycopg2
from urllib.parse import urlparse


def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL environment variable is not set.")
        sys.exit(1)

    try:
        # psycopg2 supports a connect_timeout parameter via dsn or kwargs
        conn = psycopg2.connect(dsn=database_url, connect_timeout=5)
        conn.close()
        print("OK: Connected to the database.")
        sys.exit(0)
    except Exception as e:
        print("ERROR: Could not connect to the database:")
        print(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
