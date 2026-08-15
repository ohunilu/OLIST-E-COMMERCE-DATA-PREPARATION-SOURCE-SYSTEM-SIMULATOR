"""
Transform Olist seller data into a clean simulated source-system dataset.

Input:
    /app/source_data/olist_sellers_dataset.csv

Output:
    /app/simulated_data/sellers.csv

Purpose:
    Prepare the Olist seller dataset for loading into the simulated
    PostgreSQL operational source system used by the CustomerPulse project.

Design principles:
    - Preserve all source seller records.
    - Preserve seller identifiers.
    - Do not introduce synthetic seller attributes.
    - Do not apply temporal transformations because the dataset contains
      no timestamp fields.
    - Standardize textual fields conservatively.
    - Fail fast on structural or data-quality violations.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from seller_util.seller_config import (
    OUTPUT_FILE,
    SOURCE_FILE,
)
from seller_util.seller_io import (
    read_source_data as _read_source_data,
    validate_file_exists as _validate_file_exists,
    write_output as _write_output,
)
from seller_util.seller_transform import (
    standardize_text_fields as _standardize_text_fields,
    transform_sellers as _transform_sellers,
)
from seller_util.seller_validation import (
    validate_numeric_values as _validate_numeric_values,
    validate_output as _validate_output,
    validate_required_fields as _validate_required_fields,
    validate_seller_keys as _validate_seller_keys,
    validate_source_schema as _validate_source_schema,
    validate_state_values as _validate_state_values,
)

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# File validation
def validate_file_exists(
    path: Path,
    description: str,
) -> None:
    _validate_file_exists(path, description)

# Schema validation
def validate_source_schema(df: pd.DataFrame) -> None:
    _validate_source_schema(df)

# Seller key validation
def validate_seller_keys(df: pd.DataFrame) -> None:
    _validate_seller_keys(df)

# Required field validation
def validate_required_fields(df: pd.DataFrame) -> None:
    _validate_required_fields(df)

# Text standardization
def standardize_text_fields(df: pd.DataFrame) -> pd.DataFrame:
    return _standardize_text_fields(df)

# Numeric validation
def validate_numeric_values(df: pd.DataFrame) -> None:
    _validate_numeric_values(df)

# State validation
def validate_state_values(df: pd.DataFrame) -> None:
    _validate_state_values(df)

# Output validation
def validate_output(
    df: pd.DataFrame,
    source_record_count: int,
) -> None:
    _validate_output(df, source_record_count)

# Main transformation
def transform_sellers(df: pd.DataFrame) -> pd.DataFrame:
    return _transform_sellers(df)


def main() -> None:
    logger.info("Starting Olist sellers dataset transformation.")

    validate_file_exists(
        SOURCE_FILE,
        "Seller source file",
    )

    logger.info("Reading source file: %s", SOURCE_FILE)

    sellers_df = _read_source_data()
    source_record_count = len(sellers_df)

    logger.info(
        "Source records loaded: %s",
        f"{source_record_count:,}",
    )

    validate_source_schema(sellers_df)
    validate_seller_keys(sellers_df)
    validate_required_fields(sellers_df)
    validate_numeric_values(sellers_df)

    sellers_df = standardize_text_fields(sellers_df)
    validate_state_values(sellers_df)

    validate_output(
        sellers_df,
        source_record_count,
    )

    _write_output(sellers_df)

    logger.info("Output file written: %s", OUTPUT_FILE)

    logger.info("Seller transformation completed successfully.")

    logger.info(
        "Source records: %s",
        f"{source_record_count:,}",
    )

    logger.info(
        "Output records: %s",
        f"{len(sellers_df):,}",
    )

    logger.info(
        "Output file: %s",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()