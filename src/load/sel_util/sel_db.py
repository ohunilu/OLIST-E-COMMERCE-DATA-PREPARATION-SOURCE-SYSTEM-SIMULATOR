"""
Database operations for PostgreSQL execution and bulk COPY loading.
"""

import psycopg2
from psycopg2 import sql
from sel_util.sel_config import (
    COPY_SQL,
    CREATE_TABLE_SQL,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    SCHEMA_NAME,
    SOURCE_FILE,
    TABLE_NAME,
    SellerLoadError,
    logger,
)


def get_connection():
    """Establish and return a connection to PostgreSQL."""
    if not DB_PASSWORD:
        raise SellerLoadError("POSTGRES_PASSWORD environment variable is not set.")

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
    """Ensure the target schema and table exist."""
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


def bulk_load(conn) -> None:
    """Stream raw CSV contents directly into PostgreSQL via COPY FROM STDIN."""
    logger.info("Starting bulk load into %s.%s.", SCHEMA_NAME, TABLE_NAME)

    with conn.cursor() as cur:
        with SOURCE_FILE.open("r", encoding="utf-8") as file_handle:
            cur.copy_expert(
                COPY_SQL.as_string(conn),
                file_handle,
            )

    logger.info("Sellers bulk load completed successfully.")


def create_indexes(conn) -> None:
    """Create indexes for prefix and location lookup optimization."""
    logger.info("Creating seller indexes.")

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                """
                CREATE INDEX IF NOT EXISTS idx_sellers_zip_code
                ON {}.{} (seller_zip_code_prefix)
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

        cur.execute(
            sql.SQL(
                """
                CREATE INDEX IF NOT EXISTS idx_sellers_state
                ON {}.{} (seller_state)
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

    logger.info("Seller indexes created successfully.")