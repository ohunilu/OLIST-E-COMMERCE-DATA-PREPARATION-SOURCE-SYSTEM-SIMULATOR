#!/usr/bin/env python3
"""
Load transformed customers data into PostgreSQL.

Source:
    /app/simulated_data/customers.csv

Target:
    ecommerce.customers

Design principles:
    - Idempotent table creation
    - Never silently append to an already-populated table
    - Transactional loading
    - PostgreSQL COPY for efficient bulk loading
    - Post-load row-count validation
    - Primary-key validation
    - Required-column validation
    - Clear production-style logging
    - Configuration through environment variables

Expected customers schema:

    customer_id
    customer_unique_id
    first_name
    last_name
    email
    phone
    address_line_1
    city
    state
    zip_code_prefix
    country
    signup_date
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_FILE = Path(
    os.getenv(
        "CUSTOMERS_SOURCE_FILE",
        "/app/simulated_data/customers.csv",
    )
)

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

TARGET_SCHEMA = os.getenv("POSTGRES_SCHEMA", "public")
TARGET_TABLE = "customers"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Expected schema
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS = [
    "customer_id",
    "customer_unique_id",
    "first_name",
    "last_name",
    "email",
    "phone",
    "address_line_1",
    "city",
    "state",
    "zip_code_prefix",
    "country",
    "signup_date",
]


# ---------------------------------------------------------------------------
# PostgreSQL DDL
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {schema}.{table} (
    customer_id         TEXT PRIMARY KEY,
    customer_unique_id  TEXT NOT NULL,
    first_name          TEXT NOT NULL,
    last_name           TEXT NOT NULL,
    email               TEXT NOT NULL,
    phone               TEXT NOT NULL,
    address_line_1      TEXT NOT NULL,
    city                TEXT NOT NULL,
    state               CHAR(2) NOT NULL,
    zip_code_prefix     INTEGER NOT NULL,
    country             TEXT NOT NULL,
    signup_date         TIMESTAMP NOT NULL
);
"""


CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_customers_customer_unique_id
    ON {schema}.{table} (customer_unique_id);

CREATE INDEX IF NOT EXISTS idx_customers_signup_date
    ON {schema}.{table} (signup_date);

CREATE INDEX IF NOT EXISTS idx_customers_zip_code_prefix
    ON {schema}.{table} (zip_code_prefix);
"""


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Source validation
# ---------------------------------------------------------------------------

def validate_source_file() -> None:
    """Validate that the transformed customers file exists."""

    logger.info("Reading customers source file: %s", SOURCE_FILE)

    if not SOURCE_FILE.exists():
        raise FileNotFoundError(
            f"Customers source file does not exist: {SOURCE_FILE}"
        )

    if not SOURCE_FILE.is_file():
        raise ValueError(
            f"Customers source path is not a regular file: {SOURCE_FILE}"
        )

    if SOURCE_FILE.stat().st_size == 0:
        raise ValueError(
            f"Customers source file is empty: {SOURCE_FILE}"
        )

    logger.info(
        "Customers source file validation passed."
    )


def get_source_row_count() -> int:
    """
    Count source records without loading the entire CSV into memory.

    Assumes the first line is the CSV header.
    """

    with SOURCE_FILE.open("r", encoding="utf-8", newline="") as file:
        row_count = sum(1 for _ in file) - 1

    if row_count < 0:
        raise ValueError(
            "Customers source file does not contain a valid CSV header."
        )

    logger.info(
        "Source records available for loading: %s",
        f"{row_count:,}",
    )

    return row_count


def validate_source_header() -> None:
    """Validate the CSV header against the expected customers schema."""

    with SOURCE_FILE.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        header_line = file.readline().strip()

    if not header_line:
        raise ValueError("Customers CSV does not contain a header.")

    actual_columns = [
        column.strip().strip('"')
        for column in header_line.split(",")
    ]

    if actual_columns != EXPECTED_COLUMNS:
        raise ValueError(
            "Customers source schema mismatch.\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Found:    {actual_columns}"
        )

    logger.info("Customers source schema validation passed.")


# ---------------------------------------------------------------------------
# Target table management
# ---------------------------------------------------------------------------

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
        sql.SQL(
            "SELECT COUNT(*) FROM {}.{}"
        ).format(
            sql.Identifier(TARGET_SCHEMA),
            sql.Identifier(TARGET_TABLE),
        )
    )

    return cursor.fetchone()[0]


def validate_target_is_loadable(cursor) -> None:
    """
    Prevent accidental duplicate loads.

    Existing empty table:
        allowed

    Existing populated table:
        fail
    """

    row_count = get_target_row_count(cursor)

    if row_count > 0:
        raise RuntimeError(
            f"Target table {TARGET_SCHEMA}.{TARGET_TABLE} already "
            f"contains {row_count:,} records. "
            "Loading has been aborted to prevent duplicate data."
        )

    logger.info(
        "Target table is empty and ready for loading."
    )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_customers(cursor) -> None:
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

    with SOURCE_FILE.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        cursor.copy_expert(copy_sql.as_string(cursor), file)

    logger.info(
        "Customers bulk load completed successfully."
    )


# ---------------------------------------------------------------------------
# Post-load validation
# ---------------------------------------------------------------------------

def validate_row_count(
    cursor,
    expected_count: int,
) -> None:
    """Validate source and target row counts."""

    actual_count = get_target_row_count(cursor)

    if actual_count != expected_count:
        raise RuntimeError(
            "Customers row-count validation failed. "
            f"Expected={expected_count:,}, "
            f"Actual={actual_count:,}"
        )

    logger.info(
        "Customers row-count validation passed: %s records.",
        f"{actual_count:,}",
    )


def validate_primary_key(cursor) -> None:
    """Validate that customer_id is populated and unique."""

    cursor.execute(
        sql.SQL(
            """
            SELECT
                COUNT(*) AS total_rows,
                COUNT(customer_id) AS non_null_ids,
                COUNT(DISTINCT customer_id) AS unique_ids
            FROM {}.{}
            """
        ).format(
            sql.Identifier(TARGET_SCHEMA),
            sql.Identifier(TARGET_TABLE),
        )
    )

    total_rows, non_null_ids, unique_ids = cursor.fetchone()

    if non_null_ids != total_rows:
        raise RuntimeError(
            "Customer primary-key validation failed: "
            "NULL customer_id values detected."
        )

    if unique_ids != total_rows:
        raise RuntimeError(
            "Customer primary-key validation failed: "
            "duplicate customer_id values detected."
        )

    logger.info(
        "Customer primary-key validation passed."
    )


def validate_required_fields(cursor) -> None:
    """Validate required customer fields after loading."""

    required_columns = [
        "customer_id",
        "customer_unique_id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "address_line_1",
        "city",
        "state",
        "zip_code_prefix",
        "country",
        "signup_date",
    ]

    for column in required_columns:
        cursor.execute(
            sql.SQL(
                """
                SELECT COUNT(*)
                FROM {}.{}
                WHERE {} IS NULL
                """
            ).format(
                sql.Identifier(TARGET_SCHEMA),
                sql.Identifier(TARGET_TABLE),
                sql.Identifier(column),
            )
        )

        null_count = cursor.fetchone()[0]

        if null_count != 0:
            raise RuntimeError(
                f"Required field validation failed: "
                f"{column} contains {null_count:,} NULL values."
            )

    logger.info(
        "Customers required-field validation passed."
    )


def validate_signup_dates(cursor) -> None:
    """Validate that signup_date contains valid temporal values."""

    cursor.execute(
        sql.SQL(
            """
            SELECT
                MIN(signup_date),
                MAX(signup_date),
                COUNT(signup_date)
            FROM {}.{}
            """
        ).format(
            sql.Identifier(TARGET_SCHEMA),
            sql.Identifier(TARGET_TABLE),
        )
    )

    minimum, maximum, non_null_count = cursor.fetchone()

    if non_null_count == 0:
        raise RuntimeError(
            "signup_date validation failed: no populated signup dates."
        )

    logger.info(
        "Customer signup_date validation passed."
    )

    logger.info(
        "Signup date range: %s to %s",
        minimum,
        maximum,
    )


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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Execute the customers loading pipeline."""

    logger.info("=" * 60)
    logger.info("Starting Olist customers data load.")
    logger.info("=" * 60)

    connection = None

    try:
        # ---------------------------------------------------------------
        # Source validation
        # ---------------------------------------------------------------

        validate_source_file()
        validate_source_header()

        source_row_count = get_source_row_count()

        # ---------------------------------------------------------------
        # Database connection
        # ---------------------------------------------------------------

        connection = get_connection()
        connection.autocommit = False

        logger.info(
            "PostgreSQL connection established successfully."
        )

        with connection.cursor() as cursor:

            # -----------------------------------------------------------
            # Target preparation
            # -----------------------------------------------------------

            ensure_schema_and_table(cursor)

            validate_target_is_loadable(cursor)

            # -----------------------------------------------------------
            # Data loading
            # -----------------------------------------------------------

            load_customers(cursor)

            # -----------------------------------------------------------
            # Post-load validation
            # -----------------------------------------------------------

            validate_row_count(
                cursor,
                source_row_count,
            )

            validate_primary_key(cursor)

            validate_required_fields(cursor)

            validate_signup_dates(cursor)

            # -----------------------------------------------------------
            # Index creation
            # -----------------------------------------------------------

            create_indexes(cursor)

        # ---------------------------------------------------------------
        # Commit transaction
        # ---------------------------------------------------------------

        connection.commit()

        logger.info(
            "Customers transaction committed successfully."
        )

        logger.info("=" * 60)
        logger.info(
            "Customers load completed successfully."
        )
        logger.info(
            "Source records: %s",
            f"{source_row_count:,}",
        )
        logger.info(
            "Target table: %s.%s",
            TARGET_SCHEMA,
            TARGET_TABLE,
        )
        logger.info(
            "Target records: %s",
            f"{source_row_count:,}",
        )
        logger.info("=" * 60)

        return 0

    except Exception as exc:
        logger.error(
            "Customers load FAILED: %s",
            exc,
        )

        if connection is not None:
            try:
                connection.rollback()
                logger.error(
                    "Transaction rolled back successfully."
                )
            except Exception as rollback_error:
                logger.error(
                    "Transaction rollback failed: %s",
                    rollback_error,
                )

        return 1

    finally:
        if connection is not None:
            connection.close()
            logger.info(
                "PostgreSQL connection closed."
            )


if __name__ == "__main__":
    sys.exit(main())