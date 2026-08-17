#!/usr/bin/env python3

import logging
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2 import sql


# ============================================================
# Configuration
# ============================================================

SOURCE_FILE = Path("/app/simulated_data/sellers.csv")

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce_source")
DB_USER = os.getenv("POSTGRES_USER", "olist_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")

SCHEMA_NAME = "public"
TABLE_NAME = "sellers"

EXPECTED_COLUMNS = [
    "seller_id",
    "seller_zip_code_prefix",
    "seller_city",
    "seller_state",
]

REQUIRED_COLUMNS = [
    "seller_id",
    "seller_zip_code_prefix",
    "seller_city",
    "seller_state",
]


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# Exceptions
# ============================================================

class SellerLoadError(Exception):
    """Raised when seller validation or loading fails."""


# ============================================================
# Source validation
# ============================================================

def validate_source_file() -> pd.DataFrame:
    logger.info("Reading sellers source file: %s", SOURCE_FILE)

    if not SOURCE_FILE.exists():
        raise SellerLoadError(
            f"Sellers source file does not exist: {SOURCE_FILE}"
        )

    if SOURCE_FILE.stat().st_size == 0:
        raise SellerLoadError(
            f"Sellers source file is empty: {SOURCE_FILE}"
        )

    logger.info("Sellers source file validation passed.")

    df = pd.read_csv(SOURCE_FILE)

    actual_columns = df.columns.tolist()

    missing_columns = [
        column
        for column in EXPECTED_COLUMNS
        if column not in actual_columns
    ]

    unexpected_columns = [
        column
        for column in actual_columns
        if column not in EXPECTED_COLUMNS
    ]

    if missing_columns or unexpected_columns:
        raise SellerLoadError(
            "Sellers source schema mismatch. "
            f"Missing columns: {missing_columns}; "
            f"Unexpected columns: {unexpected_columns}"
        )

    logger.info("Sellers source schema validation passed.")

    logger.info(
        "Source records available for loading: %s",
        f"{len(df):,}",
    )

    if len(df) == 0:
        raise SellerLoadError("Sellers source contains zero records.")

    # --------------------------------------------------------
    # Primary key validation
    # --------------------------------------------------------

    if df["seller_id"].isna().any():
        count = int(df["seller_id"].isna().sum())
        raise SellerLoadError(
            f"Seller primary-key validation failed: "
            f"{count:,} NULL seller_id values."
        )

    duplicate_count = int(
        df["seller_id"].duplicated().sum()
    )

    if duplicate_count > 0:
        raise SellerLoadError(
            f"Seller primary-key validation failed: "
            f"{duplicate_count:,} duplicate seller_id values."
        )

    logger.info("Seller primary-key validation passed.")

    # --------------------------------------------------------
    # Required-field validation
    # --------------------------------------------------------

    null_counts = df[REQUIRED_COLUMNS].isna().sum()

    invalid_required = {
        column: int(count)
        for column, count in null_counts.items()
        if count > 0
    }

    if invalid_required:
        raise SellerLoadError(
            "Sellers required-field validation failed: "
            f"{invalid_required}"
        )

    logger.info("Sellers required-field validation passed.")

    # --------------------------------------------------------
    # ZIP code validation
    # --------------------------------------------------------

    zip_numeric = pd.to_numeric(
        df["seller_zip_code_prefix"],
        errors="coerce",
    )

    invalid_zip = (
        zip_numeric.isna()
        | (zip_numeric < 0)
        | (zip_numeric > 99999)
        | (zip_numeric % 1 != 0)
    )

    invalid_zip_count = int(invalid_zip.sum())

    if invalid_zip_count > 0:
        raise SellerLoadError(
            "Seller ZIP code validation failed: "
            f"{invalid_zip_count:,} invalid values."
        )

    logger.info("Seller ZIP code validation passed.")

    # --------------------------------------------------------
    # State validation
    # --------------------------------------------------------

    state_values = (
        df["seller_state"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    invalid_state = (
        state_values.isna()
        | (state_values.str.len() != 2)
    )

    invalid_state_count = int(invalid_state.sum())

    if invalid_state_count > 0:
        raise SellerLoadError(
            "Seller state validation failed: "
            f"{invalid_state_count:,} invalid state values."
        )

    logger.info(
        "Seller state validation passed: %s unique states.",
        state_values.nunique(),
    )

    # --------------------------------------------------------
    # Text-field validation
    # --------------------------------------------------------

    for column in ["seller_city", "seller_state"]:
        empty_count = int(
            df[column]
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        )

        if empty_count > 0:
            raise SellerLoadError(
                f"Sellers text validation failed: "
                f"{empty_count:,} empty values in {column}."
            )

    logger.info("Seller text-field validation passed.")

    return df


# ============================================================
# Database connection
# ============================================================

def get_connection():
    if not DB_PASSWORD:
        raise SellerLoadError(
            "POSTGRES_PASSWORD environment variable is not set."
        )

    logger.info(
        "Connecting to PostgreSQL: host=%s port=%s "
        "database=%s user=%s",
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


# ============================================================
# Target table creation / validation
# ============================================================

def ensure_target_table(conn):
    logger.info(
        "Ensuring PostgreSQL schema exists: %s",
        SCHEMA_NAME,
    )

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(SCHEMA_NAME)
            )
        )

        logger.info(
            "Ensuring target table exists: %s.%s",
            SCHEMA_NAME,
            TABLE_NAME,
        )

        cur.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {}.{} (
                    seller_id VARCHAR(64) NOT NULL,
                    seller_zip_code_prefix INTEGER NOT NULL,
                    seller_city TEXT NOT NULL,
                    seller_state VARCHAR(2) NOT NULL,

                    CONSTRAINT sellers_pkey
                        PRIMARY KEY (seller_id)
                )
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

    logger.info("Target table validation/creation passed.")


# ============================================================
# Target table state validation
# ============================================================

def validate_target_empty(conn):
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                "SELECT COUNT(*) FROM {}.{}"
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

        count = cur.fetchone()[0]

    if count != 0:
        raise SellerLoadError(
            f"Target table {SCHEMA_NAME}.{TABLE_NAME} "
            f"is not empty. Existing records: {count:,}"
        )

    logger.info(
        "Target table is empty and ready for loading."
    )


# ============================================================
# Bulk load
# ============================================================

def bulk_load(conn):
    logger.info(
        "Starting bulk load into %s.%s.",
        SCHEMA_NAME,
        TABLE_NAME,
    )

    copy_sql = sql.SQL(
        """
        COPY {}.{} (
            seller_id,
            seller_zip_code_prefix,
            seller_city,
            seller_state
        )
        FROM STDIN
        WITH (
            FORMAT CSV,
            HEADER TRUE,
            NULL ''
        )
        """
    ).format(
        sql.Identifier(SCHEMA_NAME),
        sql.Identifier(TABLE_NAME),
    )

    with conn.cursor() as cur:
        with SOURCE_FILE.open(
            "r",
            encoding="utf-8",
        ) as file_handle:
            cur.copy_expert(
                copy_sql.as_string(conn),
                file_handle,
            )

    logger.info(
        "Sellers bulk load completed successfully."
    )


# ============================================================
# Post-load validation
# ============================================================

def validate_loaded_data(conn, source_count):
    with conn.cursor() as cur:

        # ----------------------------------------------------
        # Row count
        # ----------------------------------------------------

        cur.execute(
            sql.SQL(
                "SELECT COUNT(*) FROM {}.{}"
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

        target_count = cur.fetchone()[0]

        if target_count != source_count:
            raise SellerLoadError(
                "Sellers row-count validation failed: "
                f"source={source_count:,}, "
                f"target={target_count:,}"
            )

        logger.info(
            "Sellers row-count validation passed: %s records.",
            f"{target_count:,}",
        )

        # ----------------------------------------------------
        # Primary key
        # ----------------------------------------------------

        cur.execute(
            sql.SQL(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(seller_id) AS non_null,
                    COUNT(DISTINCT seller_id) AS unique_ids
                FROM {}.{}
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

        total, non_null, unique_ids = cur.fetchone()

        if non_null != total:
            raise SellerLoadError(
                "Seller primary-key validation failed: "
                "NULL seller_id values found in target."
            )

        if unique_ids != total:
            raise SellerLoadError(
                "Seller primary-key validation failed: "
                "duplicate seller_id values found in target."
            )

        logger.info(
            "Seller primary-key validation passed."
        )

        # ----------------------------------------------------
        # Required fields
        # ----------------------------------------------------

        cur.execute(
            sql.SQL(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE seller_zip_code_prefix IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE seller_city IS NULL
                    ),
                    COUNT(*) FILTER (
                        WHERE seller_state IS NULL
                    )
                FROM {}.{}
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

        null_zip, null_city, null_state = cur.fetchone()

        if any([null_zip, null_city, null_state]):
            raise SellerLoadError(
                "Sellers required-field validation failed: "
                f"NULL ZIP={null_zip}, "
                f"NULL city={null_city}, "
                f"NULL state={null_state}"
            )

        logger.info(
            "Sellers required-field validation passed."
        )

        # ----------------------------------------------------
        # ZIP range
        # ----------------------------------------------------

        cur.execute(
            sql.SQL(
                """
                SELECT COUNT(*)
                FROM {}.{}
                WHERE seller_zip_code_prefix < 0
                   OR seller_zip_code_prefix > 99999
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

        invalid_zip_count = cur.fetchone()[0]

        if invalid_zip_count > 0:
            raise SellerLoadError(
                "Seller ZIP validation failed after load: "
                f"{invalid_zip_count:,} invalid values."
            )

        logger.info(
            "Seller ZIP validation passed."
        )


# ============================================================
# Index creation
# ============================================================

def create_indexes(conn):
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

    logger.info(
        "Seller indexes created successfully."
    )


# ============================================================
# Main
# ============================================================

def main():
    logger.info("=" * 60)
    logger.info("Starting Olist sellers data load.")
    logger.info("=" * 60)

    conn = None

    try:
        df = validate_source_file()
        source_count = len(df)

        conn = get_connection()

        ensure_target_table(conn)
        validate_target_empty(conn)

        bulk_load(conn)

        validate_loaded_data(
            conn,
            source_count,
        )

        create_indexes(conn)

        conn.commit()

        logger.info(
            "Sellers transaction committed successfully."
        )

        logger.info("=" * 60)
        logger.info("Sellers load completed successfully.")
        logger.info(
            "Source records: %s",
            f"{source_count:,}",
        )
        logger.info(
            "Target table: %s.%s",
            SCHEMA_NAME,
            TABLE_NAME,
        )
        logger.info(
            "Target records: %s",
            f"{source_count:,}",
        )
        logger.info("=" * 60)

    except Exception as exc:
        if conn is not None:
            conn.rollback()

        logger.error(
            "Sellers load FAILED: %s",
            exc,
        )

        sys.exit(1)

    finally:
        if conn is not None:
            conn.close()
            logger.info(
                "PostgreSQL connection closed."
            )


if __name__ == "__main__":
    main()