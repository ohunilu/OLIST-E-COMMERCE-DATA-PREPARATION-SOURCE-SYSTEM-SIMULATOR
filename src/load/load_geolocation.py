#!/usr/bin/env python3

"""
Load transformed Olist geolocation data into PostgreSQL.

Source:
    /app/simulated_data/geolocation.csv

Target:
    public.geolocation

The Olist geolocation dataset contains multiple observations per
ZIP-code prefix. Therefore, geolocation_zip_code_prefix is NOT
treated as a primary key.

The loader preserves:
    - all source records
    - exact duplicate records
    - multiple observations per ZIP prefix

Validation includes:
    - source file existence
    - source schema
    - row count
    - required fields
    - ZIP-code prefix validity
    - latitude range
    - longitude range
    - state-code validation
    - duplicate preservation
    - target row-count validation
"""

import io
import logging
import os
import sys

import pandas as pd
import psycopg2
from psycopg2 import sql


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

SOURCE_FILE = "/app/simulated_data/geolocation.csv"

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce_source")
DB_USER = os.getenv("POSTGRES_USER", "olist_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "olist_password")

DB_SCHEMA = "public"
TARGET_TABLE = "geolocation"


EXPECTED_COLUMNS = [
    "geolocation_zip_code_prefix",
    "geolocation_lat",
    "geolocation_lng",
    "geolocation_city",
    "geolocation_state",
]


EXPECTED_STATES = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------

def validate_source_file() -> None:
    """Validate that the source file exists and is readable."""

    if not os.path.exists(SOURCE_FILE):
        raise FileNotFoundError(
            f"Geolocation source file not found: {SOURCE_FILE}"
        )

    if os.path.getsize(SOURCE_FILE) == 0:
        raise ValueError(
            f"Geolocation source file is empty: {SOURCE_FILE}"
        )

    logger.info("Geolocation source file validation passed.")


def validate_schema(df: pd.DataFrame) -> None:
    """Validate the source schema exactly."""

    actual_columns = list(df.columns)

    missing = [
        column
        for column in EXPECTED_COLUMNS
        if column not in actual_columns
    ]

    unexpected = [
        column
        for column in actual_columns
        if column not in EXPECTED_COLUMNS
    ]

    if missing or unexpected:
        raise ValueError(
            "Geolocation source schema mismatch. "
            f"Missing columns: {missing}; "
            f"Unexpected columns: {unexpected}"
        )

    logger.info("Geolocation source schema validation passed.")


def validate_required_fields(df: pd.DataFrame) -> None:
    """Validate that required fields contain no null values."""

    required_columns = [
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
    ]

    null_counts = df[required_columns].isnull().sum()

    invalid = {
        column: int(count)
        for column, count in null_counts.items()
        if count > 0
    }

    if invalid:
        raise ValueError(
            f"Geolocation required-field validation failed: {invalid}"
        )

    logger.info("Geolocation required-field validation passed.")


def validate_zip_codes(df: pd.DataFrame) -> None:
    """Validate Brazilian ZIP-code prefixes."""

    series = pd.to_numeric(
        df["geolocation_zip_code_prefix"],
        errors="coerce",
    )

    if series.isnull().any():
        raise ValueError(
            "Geolocation ZIP validation failed: "
            f"{int(series.isnull().sum())} invalid ZIP prefixes."
        )

    if not series.between(0, 99999).all():
        invalid_count = int(
            (~series.between(0, 99999)).sum()
        )

        raise ValueError(
            "Geolocation ZIP validation failed: "
            f"{invalid_count} ZIP prefixes outside 0-99999."
        )

    if not (series % 1 == 0).all():
        raise ValueError(
            "Geolocation ZIP validation failed: "
            "ZIP prefixes must be integers."
        )

    logger.info("Geolocation ZIP validation passed.")


def validate_coordinates(df: pd.DataFrame) -> None:
    """Validate geographic coordinate ranges."""

    latitude = pd.to_numeric(
        df["geolocation_lat"],
        errors="coerce",
    )

    longitude = pd.to_numeric(
        df["geolocation_lng"],
        errors="coerce",
    )

    if latitude.isnull().any():
        raise ValueError(
            "Latitude validation failed: "
            f"{int(latitude.isnull().sum())} invalid values."
        )

    if longitude.isnull().any():
        raise ValueError(
            "Longitude validation failed: "
            f"{int(longitude.isnull().sum())} invalid values."
        )

    invalid_latitude = ~latitude.between(-90, 90)
    invalid_longitude = ~longitude.between(-180, 180)

    if invalid_latitude.any():
        raise ValueError(
            "Latitude validation failed: "
            f"{int(invalid_latitude.sum())} values outside [-90, 90]."
        )

    if invalid_longitude.any():
        raise ValueError(
            "Longitude validation failed: "
            f"{int(invalid_longitude.sum())} values outside [-180, 180]."
        )

    logger.info("Geolocation coordinate validation passed.")


def validate_states(df: pd.DataFrame) -> None:
    """Validate Brazilian state codes."""

    states = set(
        df["geolocation_state"]
        .astype(str)
        .str.strip()
        .str.upper()
        .unique()
    )

    invalid_states = states - EXPECTED_STATES

    if invalid_states:
        raise ValueError(
            "Geolocation state validation failed. "
            f"Unexpected state codes: {sorted(invalid_states)}"
        )

    logger.info(
        "Geolocation state validation passed: %d unique states.",
        len(states),
    )


def analyze_duplicates(df: pd.DataFrame) -> int:
    """
    Analyze exact duplicate records.

    Duplicates are intentionally preserved because the source
    geolocation dataset contains repeated observations.
    """

    duplicate_count = int(df.duplicated().sum())

    unique_zip_count = int(
        df["geolocation_zip_code_prefix"].nunique()
    )

    multiple_zip_count = int(
        (
            df.groupby("geolocation_zip_code_prefix")
            .size()
            .gt(1)
        ).sum()
    )

    max_records_per_zip = int(
        df.groupby("geolocation_zip_code_prefix")
        .size()
        .max()
    )

    logger.info("Duplicate analysis completed.")
    logger.info(
        "Exact duplicate source records preserved: %d",
        duplicate_count,
    )
    logger.info(
        "Unique ZIP prefixes: %d",
        unique_zip_count,
    )
    logger.info(
        "ZIP prefixes with multiple observations: %d",
        multiple_zip_count,
    )
    logger.info(
        "Maximum observations for one ZIP prefix: %d",
        max_records_per_zip,
    )
    logger.info("No duplicate records will be removed.")

    return duplicate_count


# ---------------------------------------------------------------------
# PostgreSQL helpers
# ---------------------------------------------------------------------

def get_connection():
    """Create PostgreSQL connection."""

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


def ensure_schema(conn) -> None:
    """Ensure target schema exists."""

    logger.info(
        "Ensuring PostgreSQL schema exists: %s",
        DB_SCHEMA,
    )

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}")
            .format(sql.Identifier(DB_SCHEMA))
        )


def ensure_table(conn) -> None:
    """
    Create geolocation table if it does not exist.

    No primary key is defined because one ZIP prefix can have
    many observations.
    """

    logger.info(
        "Ensuring target table exists: %s.%s",
        DB_SCHEMA,
        TARGET_TABLE,
    )

    create_table_sql = sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS {}.{} (
            geolocation_zip_code_prefix INTEGER NOT NULL,
            geolocation_lat DOUBLE PRECISION NOT NULL,
            geolocation_lng DOUBLE PRECISION NOT NULL,
            geolocation_city TEXT NOT NULL,
            geolocation_state CHAR(2) NOT NULL
        )
        """
    ).format(
        sql.Identifier(DB_SCHEMA),
        sql.Identifier(TARGET_TABLE),
    )

    with conn.cursor() as cur:
        cur.execute(create_table_sql)

    logger.info("Target table validation/creation passed.")


def validate_target_is_empty(conn) -> None:
    """Ensure the target table is empty before loading."""

    query = sql.SQL(
        "SELECT COUNT(*) FROM {}.{}"
    ).format(
        sql.Identifier(DB_SCHEMA),
        sql.Identifier(TARGET_TABLE),
    )

    with conn.cursor() as cur:
        cur.execute(query)
        count = cur.fetchone()[0]

    if count != 0:
        raise ValueError(
            f"Target table {DB_SCHEMA}.{TARGET_TABLE} "
            f"is not empty. Existing records: {count}"
        )

    logger.info("Target table is empty and ready for loading.")


def bulk_load(conn, df: pd.DataFrame) -> None:
    """Bulk load the DataFrame using PostgreSQL COPY."""

    logger.info(
        "Starting bulk load into %s.%s.",
        DB_SCHEMA,
        TARGET_TABLE,
    )

    columns = [
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
    ]

    buffer = io.StringIO()

    df[columns].to_csv(
        buffer,
        index=False,
        header=False,
        na_rep="\\N",
    )

    buffer.seek(0)

    copy_sql = sql.SQL(
        """
        COPY {}.{} ({})
        FROM STDIN
        WITH CSV
        NULL AS '\\N'
        """
    ).format(
        sql.Identifier(DB_SCHEMA),
        sql.Identifier(TARGET_TABLE),
        sql.SQL(", ").join(
            sql.Identifier(column)
            for column in columns
        ),
    )

    with conn.cursor() as cur:
        cur.copy_expert(copy_sql.as_string(conn), buffer)

    logger.info(
        "Geolocation bulk load completed successfully."
    )


# ---------------------------------------------------------------------
# Post-load validation
# ---------------------------------------------------------------------

def validate_row_count(
    conn,
    expected_count: int,
) -> None:
    """Validate target row count."""

    query = sql.SQL(
        "SELECT COUNT(*) FROM {}.{}"
    ).format(
        sql.Identifier(DB_SCHEMA),
        sql.Identifier(TARGET_TABLE),
    )

    with conn.cursor() as cur:
        cur.execute(query)
        actual_count = cur.fetchone()[0]

    if actual_count != expected_count:
        raise ValueError(
            "Geolocation row-count validation failed: "
            f"expected {expected_count:,}, "
            f"found {actual_count:,}."
        )

    logger.info(
        "Geolocation row-count validation passed: %s records.",
        f"{actual_count:,}",
    )


def validate_target_duplicates(
    conn,
    expected_duplicate_count: int,
) -> None:
    """
    Validate that exact duplicates were preserved.

    We compare the number of duplicate rows in PostgreSQL
    using all five data columns.
    """

    query = sql.SQL(
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                geolocation_zip_code_prefix,
                geolocation_lat,
                geolocation_lng,
                geolocation_city,
                geolocation_state,
                COUNT(*) AS record_count
            FROM {}.{}
            GROUP BY
                geolocation_zip_code_prefix,
                geolocation_lat,
                geolocation_lng,
                geolocation_city,
                geolocation_state
            HAVING COUNT(*) > 1
        ) duplicate_groups
        """
    ).format(
        sql.Identifier(DB_SCHEMA),
        sql.Identifier(TARGET_TABLE),
    )

    with conn.cursor() as cur:
        cur.execute(query)
        duplicate_groups = cur.fetchone()[0]

    # This is a group count, not duplicate-row count.
    # We therefore validate presence rather than incorrectly
    # equating it to pandas' duplicate-row metric.
    if expected_duplicate_count > 0 and duplicate_groups == 0:
        raise ValueError(
            "Geolocation duplicate preservation validation failed: "
            "expected duplicate records/groups, but none were found."
        )

    logger.info(
        "Geolocation duplicate preservation validation passed."
    )


def validate_target_coordinates(conn) -> None:
    """Validate coordinates after loading."""

    query = sql.SQL(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE geolocation_lat < -90
                   OR geolocation_lat > 90
            ),
            COUNT(*) FILTER (
                WHERE geolocation_lng < -180
                   OR geolocation_lng > 180
            )
        FROM {}.{}
        """
    ).format(
        sql.Identifier(DB_SCHEMA),
        sql.Identifier(TARGET_TABLE),
    )

    with conn.cursor() as cur:
        cur.execute(query)
        invalid_latitude, invalid_longitude = cur.fetchone()

    if invalid_latitude:
        raise ValueError(
            f"Target latitude validation failed: "
            f"{invalid_latitude} invalid records."
        )

    if invalid_longitude:
        raise ValueError(
            f"Target longitude validation failed: "
            f"{invalid_longitude} invalid records."
        )

    logger.info(
        "Target geolocation coordinate validation passed."
    )


def create_indexes(conn) -> None:
    """Create indexes supporting downstream ZIP-code joins."""

    logger.info("Creating geolocation indexes.")

    index_statements = [
        sql.SQL(
            """
            CREATE INDEX IF NOT EXISTS
            idx_geolocation_zip_code_prefix
            ON {}.{} (geolocation_zip_code_prefix)
            """
        ).format(
            sql.Identifier(DB_SCHEMA),
            sql.Identifier(TARGET_TABLE),
        ),
        sql.SQL(
            """
            CREATE INDEX IF NOT EXISTS
            idx_geolocation_state
            ON {}.{} (geolocation_state)
            """
        ).format(
            sql.Identifier(DB_SCHEMA),
            sql.Identifier(TARGET_TABLE),
        ),
    ]

    with conn.cursor() as cur:
        for statement in index_statements:
            cur.execute(statement)

    logger.info(
        "Geolocation indexes created successfully."
    )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> int:

    logger.info("=" * 60)
    logger.info(
        "Starting Olist geolocation data load."
    )
    logger.info("=" * 60)

    conn = None

    try:
        # -------------------------------------------------------------
        # Source validation
        # -------------------------------------------------------------

        validate_source_file()

        logger.info(
            "Reading geolocation source file: %s",
            SOURCE_FILE,
        )

        df = pd.read_csv(SOURCE_FILE)

        validate_schema(df)

        source_count = len(df)

        logger.info(
            "Source records available for loading: %s",
            f"{source_count:,}",
        )

        validate_required_fields(df)
        validate_zip_codes(df)
        validate_coordinates(df)
        validate_states(df)

        expected_duplicate_count = analyze_duplicates(df)

        # -------------------------------------------------------------
        # PostgreSQL
        # -------------------------------------------------------------

        conn = get_connection()

        ensure_schema(conn)
        ensure_table(conn)
        validate_target_is_empty(conn)

        # -------------------------------------------------------------
        # Load
        # -------------------------------------------------------------

        bulk_load(conn, df)

        # -------------------------------------------------------------
        # Post-load validation
        # -------------------------------------------------------------

        validate_row_count(
            conn,
            source_count,
        )

        validate_target_duplicates(
            conn,
            expected_duplicate_count,
        )

        validate_target_coordinates(conn)

        # -------------------------------------------------------------
        # Indexes
        # -------------------------------------------------------------

        create_indexes(conn)

        # -------------------------------------------------------------
        # Commit
        # -------------------------------------------------------------

        conn.commit()

        logger.info(
            "Geolocation transaction committed successfully."
        )

        logger.info("=" * 60)
        logger.info(
            "Geolocation load completed successfully."
        )
        logger.info(
            "Source records: %s",
            f"{source_count:,}",
        )
        logger.info(
            "Target table: %s.%s",
            DB_SCHEMA,
            TARGET_TABLE,
        )
        logger.info(
            "Target records: %s",
            f"{source_count:,}",
        )
        logger.info(
            "Unique ZIP prefixes: %s",
            f"{df['geolocation_zip_code_prefix'].nunique():,}",
        )
        logger.info(
            "Exact duplicate source records preserved: %s",
            f"{expected_duplicate_count:,}",
        )
        logger.info("=" * 60)

        return 0

    except Exception as exc:

        logger.error(
            "Geolocation load FAILED: %s",
            exc,
        )

        if conn is not None:
            conn.rollback()
            logger.error(
                "Geolocation transaction rolled back."
            )

        return 1

    finally:

        if conn is not None:
            conn.close()
            logger.info(
                "PostgreSQL connection closed."
            )


if __name__ == "__main__":
    sys.exit(main())