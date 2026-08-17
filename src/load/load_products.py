"""
Load transformed Olist products data into PostgreSQL.

Source:
    /app/simulated_data/products.csv

Target:
    public.products

The loader performs:
    - Source file validation
    - Source schema validation
    - Product primary-key validation
    - Required-field validation
    - PostgreSQL target table creation/validation
    - Bulk loading
    - Target row-count validation
    - Target primary-key validation
    - Required-field validation
    - Index creation
    - Transactional commit/rollback
"""

import logging
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_FILE = Path("/app/simulated_data/products.csv")

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce_source")
DB_USER = os.getenv("POSTGRES_USER", "olist_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")

SCHEMA_NAME = "public"
TABLE_NAME = "products"


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
    "product_id",
    "product_category_name",
    "product_name_lenght",
    "product_description_lenght",
    "product_photos_qty",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
]

REQUIRED_COLUMNS = [
    "product_id",
]


# ---------------------------------------------------------------------------
# PostgreSQL schema
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.products (
    product_id                  VARCHAR(64) PRIMARY KEY,
    product_category_name      TEXT,
    product_name_lenght        INTEGER,
    product_description_lenght INTEGER,
    product_photos_qty         INTEGER,
    product_weight_g            NUMERIC,
    product_length_cm           NUMERIC,
    product_height_cm           NUMERIC,
    product_width_cm            NUMERIC
);
"""


INSERT_SQL = """
INSERT INTO public.products (
    product_id,
    product_category_name,
    product_name_lenght,
    product_description_lenght,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm
)
VALUES %s
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fail(message: str) -> None:
    """Log an error and terminate execution."""
    logger.error(message)
    raise RuntimeError(message)


def validate_source_file() -> pd.DataFrame:
    """Read and validate the transformed products dataset."""

    logger.info("Reading products source file: %s", SOURCE_FILE)

    if not SOURCE_FILE.exists():
        fail(f"Products source file does not exist: {SOURCE_FILE}")

    if SOURCE_FILE.stat().st_size == 0:
        fail(f"Products source file is empty: {SOURCE_FILE}")

    logger.info("Products source file validation passed.")

    df = pd.read_csv(SOURCE_FILE)

    if df.empty:
        fail("Products source dataset contains zero records.")

    logger.info("Products source schema validation started.")

    actual_columns = df.columns.tolist()

    if actual_columns != EXPECTED_COLUMNS:
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

        fail(
            "Products source schema mismatch. "
            f"Missing columns: {missing}; "
            f"Unexpected columns: {unexpected}"
        )

    logger.info("Products source schema validation passed.")
    logger.info("Source records available for loading: %s", f"{len(df):,}")

    return df


def validate_source_data(df: pd.DataFrame) -> None:
    """Validate product-level source integrity."""

    # -----------------------------------------------------------------------
    # Primary key
    # -----------------------------------------------------------------------

    if df["product_id"].isna().any():
        fail("Product primary-key validation failed: NULL product_id found.")

    duplicate_count = df["product_id"].duplicated().sum()

    if duplicate_count > 0:
        fail(
            "Product primary-key validation failed: "
            f"{duplicate_count:,} duplicate product_id values found."
        )

    logger.info("Product primary-key validation passed.")

    # -----------------------------------------------------------------------
    # Required fields
    # -----------------------------------------------------------------------

    null_counts = df[REQUIRED_COLUMNS].isna().sum()

    invalid_required = {
        column: int(count)
        for column, count in null_counts.items()
        if count > 0
    }

    if invalid_required:
        fail(
            "Products required-field validation failed: "
            f"{invalid_required}"
        )

    logger.info("Products required-field validation passed.")

    # -----------------------------------------------------------------------
    # Numeric validation
    # -----------------------------------------------------------------------

    numeric_columns = [
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]

    for column in numeric_columns:
        converted = pd.to_numeric(df[column], errors="coerce")

        invalid_mask = df[column].notna() & converted.isna()

        if invalid_mask.any():
            fail(
                f"Products numeric validation failed: "
                f"invalid numeric values found in {column}."
            )

    logger.info("Products numeric value validation passed.")

    # -----------------------------------------------------------------------
    # Non-negative measurements
    # -----------------------------------------------------------------------

    measurement_columns = [
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]

    for column in measurement_columns:
        numeric_values = pd.to_numeric(df[column], errors="coerce")

        negative_count = (numeric_values < 0).sum()

        if negative_count > 0:
            fail(
                f"Products value validation failed: "
                f"{negative_count:,} negative values found in {column}."
            )

    logger.info("Products non-negative value validation passed.")


def connect_postgres():
    """Create PostgreSQL connection."""

    if not DB_PASSWORD:
        fail(
            "POSTGRES_PASSWORD environment variable is not configured."
        )

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
    """Create and validate the target products table."""

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

        cur.execute(CREATE_TABLE_SQL)

    logger.info("Target table validation/creation passed.")


def validate_target_empty(conn) -> None:
    """Prevent accidental duplicate loading."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM public.products
            """
        )

        existing_rows = cur.fetchone()[0]

    if existing_rows > 0:
        fail(
            "Target table public.products is not empty. "
            f"Existing records: {existing_rows:,}. "
            "Aborting to prevent duplicate loading."
        )

    logger.info("Target table is empty and ready for loading.")


def bulk_load_products(conn, df: pd.DataFrame) -> None:
    """Bulk insert products into PostgreSQL."""

    logger.info("Starting bulk load into public.products.")

    records = []

    for row in df.itertuples(index=False, name=None):
        records.append(
            tuple(
                None if pd.isna(value) else value
                for value in row
            )
        )

    with conn.cursor() as cur:
        execute_values(
            cur,
            INSERT_SQL,
            records,
            page_size=5000,
        )

    logger.info("Products bulk load completed successfully.")


def validate_target(conn, expected_count: int) -> None:
    """Validate loaded products in PostgreSQL."""

    with conn.cursor() as cur:

        # ---------------------------------------------------------------
        # Row count
        # ---------------------------------------------------------------

        cur.execute(
            """
            SELECT COUNT(*)
            FROM public.products
            """
        )

        actual_count = cur.fetchone()[0]

        if actual_count != expected_count:
            fail(
                "Products row-count validation failed: "
                f"expected {expected_count:,}, "
                f"found {actual_count:,}."
            )

        logger.info(
            "Products row-count validation passed: %s records.",
            f"{actual_count:,}",
        )

        # ---------------------------------------------------------------
        # Primary key
        # ---------------------------------------------------------------

        cur.execute(
            """
            SELECT
                COUNT(*) AS total_rows,
                COUNT(product_id) AS non_null_ids,
                COUNT(DISTINCT product_id) AS unique_ids
            FROM public.products
            """
        )

        total_rows, non_null_ids, unique_ids = cur.fetchone()

        if (
            total_rows != non_null_ids
            or total_rows != unique_ids
        ):
            fail(
                "Product primary-key validation failed in target table."
            )

        logger.info("Product primary-key validation passed.")

        # ---------------------------------------------------------------
        # Required fields
        # ---------------------------------------------------------------

        cur.execute(
            """
            SELECT COUNT(*)
            FROM public.products
            WHERE product_id IS NULL
            """
        )

        null_product_ids = cur.fetchone()[0]

        if null_product_ids > 0:
            fail(
                "Products required-field validation failed: "
                f"{null_product_ids:,} NULL product_id values."
            )

        logger.info("Products required-field validation passed.")


def create_indexes(conn) -> None:
    """Create indexes needed for downstream joins and analysis."""

    logger.info("Creating product indexes.")

    with conn.cursor() as cur:

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_products_category
            ON public.products (product_category_name);
            """
        )

    logger.info("Product indexes created successfully.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:

    logger.info("=" * 60)
    logger.info("Starting Olist products data load.")
    logger.info("=" * 60)

    conn = None

    try:
        # ---------------------------------------------------------------
        # Source validation
        # ---------------------------------------------------------------

        df = validate_source_file()
        validate_source_data(df)

        source_count = len(df)

        # ---------------------------------------------------------------
        # PostgreSQL
        # ---------------------------------------------------------------

        conn = connect_postgres()

        ensure_target_table(conn)
        validate_target_empty(conn)

        # ---------------------------------------------------------------
        # Load
        # ---------------------------------------------------------------

        bulk_load_products(conn, df)

        # ---------------------------------------------------------------
        # Target validation
        # ---------------------------------------------------------------

        validate_target(conn, source_count)

        # ---------------------------------------------------------------
        # Indexes
        # ---------------------------------------------------------------

        create_indexes(conn)

        # ---------------------------------------------------------------
        # Commit
        # ---------------------------------------------------------------

        conn.commit()

        logger.info("Products transaction committed successfully.")

        logger.info("=" * 60)
        logger.info("Products load completed successfully.")
        logger.info("Source records: %s", f"{source_count:,}")
        logger.info("Target table: public.products")
        logger.info("Target records: %s", f"{source_count:,}")
        logger.info("=" * 60)

    except Exception as exc:

        if conn is not None:
            conn.rollback()

        logger.error("Products load FAILED: %s", exc)

        sys.exit(1)

    finally:

        if conn is not None:
            conn.close()
            logger.info("PostgreSQL connection closed.")


if __name__ == "__main__":
    main()