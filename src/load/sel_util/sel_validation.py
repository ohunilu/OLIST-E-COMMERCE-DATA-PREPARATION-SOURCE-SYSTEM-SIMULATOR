"""
Source CSV and database target validation logic for sellers data.
"""

import pandas as pd
from psycopg2 import sql
from sel_util.sel_config import (
    EXPECTED_COLUMNS,
    REQUIRED_COLUMNS,
    SCHEMA_NAME,
    SOURCE_FILE,
    TABLE_NAME,
    SellerLoadError,
    logger,
)


def validate_source_file() -> pd.DataFrame:
    """Read and validate the source sellers dataset."""
    logger.info("Reading sellers source file: %s", SOURCE_FILE)

    if not SOURCE_FILE.exists():
        raise SellerLoadError(f"Sellers source file does not exist: {SOURCE_FILE}")

    if SOURCE_FILE.stat().st_size == 0:
        raise SellerLoadError(f"Sellers source file is empty: {SOURCE_FILE}")

    logger.info("Sellers source file validation passed.")

    df = pd.read_csv(SOURCE_FILE)

    actual_columns = df.columns.tolist()
    missing_columns = [col for col in EXPECTED_COLUMNS if col not in actual_columns]
    unexpected_columns = [col for col in actual_columns if col not in EXPECTED_COLUMNS]

    if missing_columns or unexpected_columns:
        raise SellerLoadError(
            "Sellers source schema mismatch. "
            f"Missing columns: {missing_columns}; Unexpected columns: {unexpected_columns}"
        )

    logger.info("Sellers source schema validation passed.")
    logger.info("Source records available for loading: %s", f"{len(df):,}")

    if len(df) == 0:
        raise SellerLoadError("Sellers source contains zero records.")

    # Primary Key Validation
    if df["seller_id"].isna().any():
        count = int(df["seller_id"].isna().sum())
        raise SellerLoadError(
            f"Seller primary-key validation failed: {count:,} NULL seller_id values."
        )

    duplicate_count = int(df["seller_id"].duplicated().sum())
    if duplicate_count > 0:
        raise SellerLoadError(
            f"Seller primary-key validation failed: {duplicate_count:,} duplicate seller_id values."
        )

    logger.info("Seller primary-key validation passed.")

    # Required Field Validation
    null_counts = df[REQUIRED_COLUMNS].isna().sum()
    invalid_required = {col: int(cnt) for col, cnt in null_counts.items() if cnt > 0}

    if invalid_required:
        raise SellerLoadError(f"Sellers required-field validation failed: {invalid_required}")

    logger.info("Sellers required-field validation passed.")

    # ZIP Code Validation
    zip_numeric = pd.to_numeric(df["seller_zip_code_prefix"], errors="coerce")
    invalid_zip = (
        zip_numeric.isna()
        | (zip_numeric < 0)
        | (zip_numeric > 99999)
        | (zip_numeric % 1 != 0)
    )
    invalid_zip_count = int(invalid_zip.sum())

    if invalid_zip_count > 0:
        raise SellerLoadError(
            f"Seller ZIP code validation failed: {invalid_zip_count:,} invalid values."
        )

    logger.info("Seller ZIP code validation passed.")

    # State Validation
    state_values = df["seller_state"].astype(str).str.strip().str.upper()
    invalid_state = state_values.isna() | (state_values.str.len() != 2)
    invalid_state_count = int(invalid_state.sum())

    if invalid_state_count > 0:
        raise SellerLoadError(
            f"Seller state validation failed: {invalid_state_count:,} invalid state values."
        )

    logger.info("Seller state validation passed: %s unique states.", state_values.nunique())

    # Text Validation
    for column in ["seller_city", "seller_state"]:
        empty_count = int(df[column].astype(str).str.strip().eq("").sum())
        if empty_count > 0:
            raise SellerLoadError(
                f"Sellers text validation failed: {empty_count:,} empty values in {column}."
            )

    logger.info("Seller text-field validation passed.")

    return df


def validate_target_empty(conn) -> None:
    """Ensure the target PostgreSQL table is empty before copying."""
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        count = cur.fetchone()[0]

    if count != 0:
        raise SellerLoadError(
            f"Target table {SCHEMA_NAME}.{TABLE_NAME} is not empty. Existing records: {count:,}"
        )

    logger.info("Target table is empty and ready for loading.")


def validate_loaded_data(conn, source_count: int) -> None:
    """Validate target row counts, key integrity, required fields, and state after copy."""
    with conn.cursor() as cur:
        # Row Count
        cur.execute(
            sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        target_count = cur.fetchone()[0]

        if target_count != source_count:
            raise SellerLoadError(
                f"Sellers row-count validation failed: source={source_count:,}, target={target_count:,}"
            )

        logger.info("Sellers row-count validation passed: %s records.", f"{target_count:,}")

        # Primary Key
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
            raise SellerLoadError("Seller primary-key validation failed: NULL seller_id values found in target.")

        if unique_ids != total:
            raise SellerLoadError("Seller primary-key validation failed: duplicate seller_id values found in target.")

        logger.info("Seller primary-key validation passed.")

        # Required Fields
        cur.execute(
            sql.SQL(
                """
                SELECT
                    COUNT(*) FILTER (WHERE seller_zip_code_prefix IS NULL),
                    COUNT(*) FILTER (WHERE seller_city IS NULL),
                    COUNT(*) FILTER (WHERE seller_state IS NULL)
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
                f"Sellers required-field validation failed: NULL ZIP={null_zip}, NULL city={null_city}, NULL state={null_state}"
            )

        logger.info("Sellers required-field validation passed.")

        # ZIP Range Check
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
            raise SellerLoadError(f"Seller ZIP validation failed after load: {invalid_zip_count:,} invalid values.")

        logger.info("Seller ZIP validation passed.")