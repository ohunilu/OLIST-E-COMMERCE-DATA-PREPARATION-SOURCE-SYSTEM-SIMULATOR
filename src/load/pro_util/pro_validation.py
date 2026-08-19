"""
Validation routines for products CSV source data and database target integrity.
"""

import pandas as pd
from pro_util.pro_config import (
    EXPECTED_COLUMNS,
    NUMERIC_COLUMNS,
    REQUIRED_COLUMNS,
    SOURCE_FILE,
    fail,
    logger,
)


def validate_source_file() -> pd.DataFrame:
    """Read and validate the transformed products CSV file."""
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
        missing = [col for col in EXPECTED_COLUMNS if col not in actual_columns]
        unexpected = [col for col in actual_columns if col not in EXPECTED_COLUMNS]

        fail(
            "Products source schema mismatch. "
            f"Missing columns: {missing}; Unexpected columns: {unexpected}"
        )

    logger.info("Products source schema validation passed.")
    logger.info("Source records available for loading: %s", f"{len(df):,}")

    return df


def validate_source_data(df: pd.DataFrame) -> None:
    """Validate product primary key, required fields, and non-negative numeric metrics."""
    # Primary Key
    if df["product_id"].isna().any():
        fail("Product primary-key validation failed: NULL product_id found.")

    duplicate_count = df["product_id"].duplicated().sum()
    if duplicate_count > 0:
        fail(
            f"Product primary-key validation failed: {duplicate_count:,} duplicate product_id values found."
        )

    logger.info("Product primary-key validation passed.")

    # Required Fields
    null_counts = df[REQUIRED_COLUMNS].isna().sum()
    invalid_required = {col: int(cnt) for col, cnt in null_counts.items() if cnt > 0}

    if invalid_required:
        fail(f"Products required-field validation failed: {invalid_required}")

    logger.info("Products required-field validation passed.")

    # Numeric Types
    for column in NUMERIC_COLUMNS:
        converted = pd.to_numeric(df[column], errors="coerce")
        invalid_mask = df[column].notna() & converted.isna()

        if invalid_mask.any():
            fail(f"Products numeric validation failed: invalid numeric values found in {column}.")

    logger.info("Products numeric value validation passed.")

    # Non-negative Measurements
    for column in NUMERIC_COLUMNS:
        numeric_values = pd.to_numeric(df[column], errors="coerce")
        negative_count = (numeric_values < 0).sum()

        if negative_count > 0:
            fail(f"Products value validation failed: {negative_count:,} negative values found in {column}.")

    logger.info("Products non-negative value validation passed.")


def validate_target_empty(conn) -> None:
    """Ensure target table is empty to prevent duplicate loading."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM public.products")
        existing_rows = cur.fetchone()[0]

    if existing_rows > 0:
        fail(
            f"Target table public.products is not empty. Existing records: {existing_rows:,}. "
            "Aborting to prevent duplicate loading."
        )

    logger.info("Target table is empty and ready for loading.")


def validate_target(conn, expected_count: int) -> None:
    """Validate row counts, primary key uniqueness, and required fields in target table."""
    with conn.cursor() as cur:
        # Row Count
        cur.execute("SELECT COUNT(*) FROM public.products")
        actual_count = cur.fetchone()[0]

        if actual_count != expected_count:
            fail(f"Products row-count validation failed: expected {expected_count:,}, found {actual_count:,}.")

        logger.info("Products row-count validation passed: %s records.", f"{actual_count:,}")

        # Primary Key
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

        if total_rows != non_null_ids or total_rows != unique_ids:
            fail("Product primary-key validation failed in target table.")

        logger.info("Product primary-key validation passed.")

        # Required Fields
        cur.execute("SELECT COUNT(*) FROM public.products WHERE product_id IS NULL")
        null_product_ids = cur.fetchone()[0]

        if null_product_ids > 0:
            fail(f"Products required-field validation failed: {null_product_ids:,} NULL product_id values.")

        logger.info("Products required-field validation passed.")