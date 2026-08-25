"""
Database execution routines and schema inspection helpers.
"""

from typing import List, Any
import psycopg2
from psycopg2 import sql
from cross_audit_util.cross_audit_config import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    SCHEMA,
    logger,
)


def connect_database():
    """Establish and return connection to PostgreSQL target."""
    logger.info(
        "Connecting to PostgreSQL: host=%s port=%s database=%s user=%s",
        DB_HOST,
        DB_PORT,
        DB_NAME,
        DB_USER,
    )

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

    logger.info("PostgreSQL connection established successfully.")
    return conn


def table_exists(cur, table_name: str) -> bool:
    """Check if table exists in configured target schema."""
    query = """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_name = %s
        )
    """
    cur.execute(query, (SCHEMA, table_name))
    return cur.fetchone()[0]


def get_table_columns(cur, table_name: str) -> List[str]:
    """Retrieve column names for target table ordered by ordinal position."""
    query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position
    """
    cur.execute(query, (SCHEMA, table_name))
    return [row[0] for row in cur.fetchall()]


def execute_scalar(cur, query: str, params: tuple = None) -> Any:
    """Execute raw or formatted SQL query and return first column of first row."""
    cur.execute(query, params or ())
    return cur.fetchone()[0]