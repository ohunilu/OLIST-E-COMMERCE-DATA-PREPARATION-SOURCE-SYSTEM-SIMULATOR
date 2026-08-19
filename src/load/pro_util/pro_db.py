"""
Database operations for PostgreSQL database management and bulk ingestion.
"""

import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
from pro_util.pro_config import (
    CREATE_TABLE_SQL,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    INSERT_SQL,
    SCHEMA_NAME,
    TABLE_NAME,
    fail,
    logger,
)


def connect_postgres():
    """Create and return a PostgreSQL connection."""
    if not DB_PASSWORD:
        fail("POSTGRES_PASSWORD environment variable is not configured.")

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


def ensure_target_table(conn) -> None:
    """Create schema and target products table if missing."""
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


def bulk_load_products(conn, df: pd.DataFrame) -> None:
    """Bulk insert pandas DataFrame rows into PostgreSQL."""
    logger.info("Starting bulk load into public.products.")

    records = [
        tuple(None if pd.isna(value) else value for value in row)
        for row in df.itertuples(index=False, name=None)
    ]

    with conn.cursor() as cur:
        execute_values(
            cur,
            INSERT_SQL,
            records,
            page_size=5000,
        )

    logger.info("Products bulk load completed successfully.")


def create_indexes(conn) -> None:
    """Create performance indexes for downstream queries."""
    logger.info("Creating product indexes.")

    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_products_category
            ON public.products (product_category_name);
            """
        )

    logger.info("Product indexes created successfully.")