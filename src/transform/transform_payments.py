"""
Transform Olist order payment data into a clean simulated source-system dataset.

Input:
    /app/source_data/olist_order_payments_dataset.csv

Reference:
    /app/simulated_data/orders.csv

Output:
    /app/simulated_data/payments.csv

Purpose:
    Prepare the Olist payment dataset for loading into the simulated
    PostgreSQL operational source system used by the CustomerPulse project.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from payment_util.payment_config import (
    OUTPUT_FILE,
    ORDERS_FILE,
    SOURCE_FILE,
)
from payment_util.payment_io import (
    read_orders_reference_file as _read_orders_reference_file,
    read_source_file as _read_source_file,
    validate_file_exists as _validate_file_exists,
    write_output as _write_output,
)
from payment_util.payment_transform import (
    transform_payments as _transform_payments,
)
from payment_util.payment_validation import (
    log_payment_statistics as _log_payment_statistics,
    standardize_payment_type as _standardize_payment_type,
    validate_numeric_values as _validate_numeric_values,
    validate_order_references as _validate_order_references,
    validate_output as _validate_output,
    validate_payment_keys as _validate_payment_keys,
    validate_required_fields as _validate_required_fields,
    validate_source_schema as _validate_source_schema,
)

# Logging Configuration

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

# File validation
def validate_file_exists(path: Path, description: str) -> None:
    _validate_file_exists(path, description)


# Schema validation
def validate_source_schema(df: pd.DataFrame) -> None:
    _validate_source_schema(df)


# Key validation
def validate_payment_keys(df: pd.DataFrame) -> None:
    _validate_payment_keys(df)


# Required field validation
def validate_required_fields(df: pd.DataFrame) -> None:
    _validate_required_fields(df)

# Payment type standardization
def standardize_payment_type(df: pd.DataFrame) -> pd.DataFrame:
    return _standardize_payment_type(df)

# Numeric validation
def validate_numeric_values(df: pd.DataFrame) -> None:
    _validate_numeric_values(df)

# Referential integrity
def validate_order_references(
    payments_df: pd.DataFrame,
    orders_df: pd.DataFrame,
) -> None:
    _validate_order_references(payments_df, orders_df)


# Payment distribution logging
def log_payment_statistics(df: pd.DataFrame) -> None:
    _log_payment_statistics(df)

# Output validation
def validate_output(df: pd.DataFrame) -> None:
    _validate_output(df)

# Transformation
def transform_payments(
    payments_df: pd.DataFrame,
    orders_df: pd.DataFrame,
) -> pd.DataFrame:
    return _transform_payments(payments_df, orders_df)

# Main transformation
def main() -> None:
    logger.info(
        "Starting Olist order payments dataset transformation."
    )

    validate_file_exists(
        SOURCE_FILE,
        "Payment source file",
    )

    validate_file_exists(
        ORDERS_FILE,
        "Transformed orders reference file",
    )

    payments_df = _read_source_file()
    orders_df = _read_orders_reference_file()

    transformed_df = transform_payments(
        payments_df,
        orders_df,
    )

    _write_output(transformed_df)

    logger.info(
        "Payment transformation completed successfully."
    )

    logger.info(
        "Source records: %s",
        f"{len(payments_df):,}",
    )

    logger.info(
        "Output records: %s",
        f"{len(transformed_df):,}",
    )

    logger.info(
        "Output file: %s",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()