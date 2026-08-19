"""
Database operations for PostgreSQL loading.
"""

from __future__ import annotations

from pathlib import Path
import psycopg2
from psycopg2 import sql

from cus_util.cus_config import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD,
    TARGET_SCHEMA,
    TARGET_TABLE,
    CREATE_TABLE_SQL,
    logger,
)


def get_connection():
    """Create and return a PostgreSQL connection."""
    logger.info(
        "Connecting to PostgreSQL: host=%s port=%s database=%s user=%s",
        DB_HOST,
        DB_PORT,
        DB_NAME,
        DB_USER,
    )

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def ensure_schema_and_table(cursor) -> None:
    """Create the target schema and customers table if required."""
    logger.info(
        "Ensuring PostgreSQL schema exists: %s",
        TARGET_SCHEMA,
    )

    cursor.execute(
        sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
            sql.Identifier(TARGET_SCHEMA)
        )
    )

    logger.info(
        "Ensuring target table exists: %s.%s",
        TARGET_SCHEMA,
        TARGET_TABLE,
    )

    cursor.execute(
        sql.SQL(CREATE_TABLE_SQL).format(
            schema=sql.Identifier(TARGET_SCHEMA),
            table=sql.Identifier(TARGET_TABLE),
        )
    )

    logger.info("Target table validation/creation passed.")


def get_target_row_count(cursor) -> int:
    """Return the current number of rows in the target table."""
    cursor.execute(
        sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
            sql.Identifier(TARGET_SCHEMA),
            sql.Identifier(TARGET_TABLE),
        )
    )
    return cursor.fetchone()[0]


def load_customers(cursor, source_file: Path) -> None:
    """Bulk-load customers CSV using PostgreSQL COPY."""
    logger.info(
        "Starting bulk load into %s.%s.",
        TARGET_SCHEMA,
        TARGET_TABLE,
    )

    copy_sql = sql.SQL(
        """
        COPY {}.{} (
            customer_id,
            customer_unique_id,
            first_name,
            last_name,
            email,
            phone,
            address_line_1,
            city,
            state,
            zip_code_prefix,
            country,
            signup_date
        )
        FROM STDIN
        WITH (
            FORMAT CSV,
            HEADER TRUE,
            DELIMITER ',',
            QUOTE '"',
            ESCAPE '"',
            NULL ''
        )
        """
    ).format(
        sql.Identifier(TARGET_SCHEMA),
        sql.Identifier(TARGET_TABLE),
    )

    with source_file.open("r", encoding="utf-8", newline="") as file:
        cursor.copy_expert(copy_sql.as_string(cursor), file)

    logger.info("Customers bulk load completed successfully.")


def create_indexes(cursor) -> None:
    """Create non-PK indexes used for downstream queries."""
    logger.info("Creating customer indexes.")

    statements = [
        sql.SQL(
            """
            CREATE INDEX IF NOT EXISTS
                idx_customers_customer_unique_id
            ON {}.{} (customer_unique_id)
            """
        ).format(
            sql.Identifier(TARGET_SCHEMA),
            sql.Identifier(TARGET_TABLE),
        ),
        sql.SQL(
            """
            CREATE INDEX IF NOT EXISTS
                idx_customers_signup_date
            ON {}.{} (signup_date)
            """
        ).format(
            sql.Identifier(TARGET_SCHEMA),
            sql.Identifier(TARGET_TABLE),
        ),
        sql.SQL(
            """
            CREATE INDEX IF NOT EXISTS
                idx_customers_zip_code_prefix
            ON {}.{} (zip_code_prefix)
            """
        ).format(
            sql.Identifier(TARGET_SCHEMA),
            sql.Identifier(TARGET_TABLE),
        ),
    ]

    for statement in statements:
        cursor.execute(statement)

    logger.info("Customer indexes created successfully.")