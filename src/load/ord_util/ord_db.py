"""
Database connectivity and query execution for orders data.
"""

import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
from ord_util.ord_config import (
    CREATE_TABLE_SQL,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    INSERT_SQL,
    SCHEMA_NAME,
    TABLE_NAME,
    OrderLoadError,
    logger,
)


def get_connection():
    """Establish and return connection to PostgreSQL."""
    if not DB_PASSWORD:
        raise OrderLoadError("POSTGRES_PASSWORD environment variable is not set.")

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


def ensure_schema_and_table(conn) -> None:
    """Ensure target schema and database table exist."""
    logger.info("Ensuring PostgreSQL schema exists: %s", SCHEMA_NAME)

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(SCHEMA_NAME)
            )
        )

        logger.info("Ensuring target table exists: %s.%s", SCHEMA_NAME, TABLE_NAME)
        cur.execute(CREATE_TABLE_SQL)

    logger.info("Target table validation/creation passed.")


def bulk_load_orders(conn, df: pd.DataFrame) -> None:
    """Bulk insert orders records using execute_values."""
    logger.info("Starting bulk load into %s.%s.", SCHEMA_NAME, TABLE_NAME)

    records = []
    for row in df.itertuples(index=False, name=None):
        cleaned = []
        for value in row:
            if pd.isna(value):
                cleaned.append(None)
            elif isinstance(value, pd.Timestamp):
                cleaned.append(value.to_pydatetime())
            else:
                cleaned.append(value)
        records.append(tuple(cleaned))

    with conn.cursor() as cur:
        execute_values(
            cur,
            INSERT_SQL.as_string(conn),
            records,
            page_size=5000,
        )

    logger.info("Orders bulk load completed successfully.")


def create_indexes(conn) -> None:
    """Create indexes for customer, purchase date, and status lookup optimization."""
    logger.info("Creating order indexes.")

    index_queries = [
        ("idx_orders_customer_id", "customer_id"),
        ("idx_orders_purchase_timestamp", "order_purchase_timestamp"),
        ("idx_orders_status", "order_status"),
    ]

    with conn.cursor() as cur:
        for idx_name, column_name in index_queries:
            cur.execute(
                sql.SQL(
                    """
                    CREATE INDEX IF NOT EXISTS {}
                    ON {}.{} ({})
                    """
                ).format(
                    sql.Identifier(idx_name),
                    sql.Identifier(SCHEMA_NAME),
                    sql.Identifier(TABLE_NAME),
                    sql.Identifier(column_name),
                )
            )

    logger.info("Order indexes created successfully.")