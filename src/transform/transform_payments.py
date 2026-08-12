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

Design principles:
    - Preserve source records and monetary values.
    - Do not apply temporal offsets because payments have no timestamp.
    - Preserve multiple payments per order.
    - Validate composite payment keys.
    - Validate referential integrity against transformed orders.
    - Standardize categorical values without inventing business data.
    - Fail fast on structural/data-quality violations.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_FILE = Path(
    "/app/source_data/olist_order_payments_dataset.csv"
)

ORDERS_FILE = Path(
    "/app/simulated_data/orders.csv"
)

OUTPUT_FILE = Path(
    "/app/simulated_data/payments.csv"
)


EXPECTED_COLUMNS = [
    "order_id",
    "payment_sequential",
    "payment_type",
    "payment_installments",
    "payment_value",
]


VALID_PAYMENT_TYPES = {
    "credit_card",
    "boleto",
    "voucher",
    "debit_card",
    "not_defined",
}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------

def validate_file_exists(path: Path, description: str) -> None:
    """Validate that an input file exists."""

    if not path.exists():
        raise FileNotFoundError(
            f"{description} not found: {path}"
        )


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def validate_source_schema(df: pd.DataFrame) -> None:
    """Validate the source payment dataset schema."""

    actual_columns = list(df.columns)

    if actual_columns != EXPECTED_COLUMNS:
        raise ValueError(
            "Unexpected payment source schema.\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Actual:   {actual_columns}"
        )

    logger.info("Source schema validation passed.")


# ---------------------------------------------------------------------------
# Key validation
# ---------------------------------------------------------------------------

def validate_payment_keys(df: pd.DataFrame) -> None:
    """
    Validate the natural composite key:

        (order_id, payment_sequential)
    """

    if df["order_id"].isna().any():
        raise ValueError(
            "order_id contains NULL values."
        )

    if df["payment_sequential"].isna().any():
        raise ValueError(
            "payment_sequential contains NULL values."
        )

    duplicate_count = df.duplicated(
        subset=["order_id", "payment_sequential"]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            "Duplicate order-payment keys detected: "
            f"{duplicate_count}"
        )

    logger.info(
        "Composite payment key validation passed."
    )


# ---------------------------------------------------------------------------
# Required field validation
# ---------------------------------------------------------------------------

def validate_required_fields(df: pd.DataFrame) -> None:
    """Validate required payment fields."""

    required_columns = EXPECTED_COLUMNS

    null_counts = df[required_columns].isna().sum()

    invalid = null_counts[null_counts > 0]

    if not invalid.empty:
        raise ValueError(
            "Required payment fields contain NULL values:\n"
            f"{invalid.to_string()}"
        )

    logger.info(
        "Required field validation passed."
    )


# ---------------------------------------------------------------------------
# Payment type standardization
# ---------------------------------------------------------------------------

def standardize_payment_type(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Standardize payment type values."""

    df["payment_type"] = (
        df["payment_type"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    unexpected_types = sorted(
        set(df["payment_type"].unique())
        - VALID_PAYMENT_TYPES
    )

    if unexpected_types:
        raise ValueError(
            "Unexpected payment types detected: "
            f"{unexpected_types}"
        )

    logger.info(
        "Payment type standardization completed."
    )

    logger.info(
        "Payment types found: %s",
        sorted(df["payment_type"].unique()),
    )

    return df


# ---------------------------------------------------------------------------
# Numeric validation
# ---------------------------------------------------------------------------

def validate_numeric_values(df: pd.DataFrame) -> None:
    """Validate payment numeric fields."""

    # Payment sequential must be a positive integer.
    if (df["payment_sequential"] < 1).any():
        invalid_count = (
            df["payment_sequential"] < 1
        ).sum()

        raise ValueError(
            "Invalid payment_sequential values detected: "
            f"{invalid_count}"
        )

    # Installments can be zero in the Olist source data.
    if (df["payment_installments"] < 0).any():
        invalid_count = (
            df["payment_installments"] < 0
        ).sum()

        raise ValueError(
            "Negative payment_installments detected: "
            f"{invalid_count}"
        )

    # Monetary values cannot be negative.
    if (df["payment_value"] < 0).any():
        invalid_count = (
            df["payment_value"] < 0
        ).sum()

        raise ValueError(
            "Negative payment_value values detected: "
            f"{invalid_count}"
        )

    logger.info(
        "Numeric value validation passed."
    )


# ---------------------------------------------------------------------------
# Referential integrity
# ---------------------------------------------------------------------------

def validate_order_references(
    payments_df: pd.DataFrame,
    orders_df: pd.DataFrame,
) -> None:
    """
    Validate that every payment references an order
    present in the transformed orders dataset.
    """

    order_ids = set(
        orders_df["order_id"].dropna()
    )

    payment_order_ids = set(
        payments_df["order_id"].dropna()
    )

    orphaned_orders = payment_order_ids - order_ids

    if orphaned_orders:
        logger.error(
            "Payment records reference orders missing from "
            "transformed orders dataset: %s",
            len(orphaned_orders),
        )

        sample = sorted(orphaned_orders)[:10]

        raise ValueError(
            "Referential integrity validation failed. "
            f"Missing order references: {len(orphaned_orders)}. "
            f"Sample: {sample}"
        )

    logger.info(
        "Order reference validation passed."
    )


# ---------------------------------------------------------------------------
# Payment distribution logging
# ---------------------------------------------------------------------------

def log_payment_statistics(
    df: pd.DataFrame,
) -> None:
    """Log useful payment characteristics."""

    payment_type_counts = (
        df["payment_type"]
        .value_counts()
        .to_dict()
    )

    multiple_payment_orders = (
        df.groupby("order_id")
        .size()
        .gt(1)
        .sum()
    )

    maximum_payments_per_order = (
        df.groupby("order_id")
        .size()
        .max()
    )

    zero_value_count = (
        df["payment_value"] == 0
    ).sum()

    logger.info(
        "Payment type distribution: %s",
        payment_type_counts,
    )

    logger.info(
        "Orders with multiple payment records: %s",
        multiple_payment_orders,
    )

    logger.info(
        "Maximum payments for one order: %s",
        maximum_payments_per_order,
    )

    logger.info(
        "Zero-value payments preserved: %s",
        zero_value_count,
    )


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------

def validate_output(df: pd.DataFrame) -> None:
    """Validate the final transformed payment dataset."""

    # Row count must remain unchanged.
    if len(df) == 0:
        raise ValueError(
            "Output payment dataset contains zero records."
        )

    # Output schema.
    if list(df.columns) != EXPECTED_COLUMNS:
        raise ValueError(
            "Output schema does not match expected schema.\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Actual:   {list(df.columns)}"
        )

    # Composite key.
    duplicate_count = df.duplicated(
        subset=["order_id", "payment_sequential"]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            "Output contains duplicate order-payment keys: "
            f"{duplicate_count}"
        )

    # No NULLs.
    if df[EXPECTED_COLUMNS].isna().any().any():
        raise ValueError(
            "Output contains unexpected NULL values."
        )

    # Payment values.
    if (df["payment_value"] < 0).any():
        raise ValueError(
            "Output contains negative payment values."
        )

    logger.info(
        "Output schema validation passed."
    )


# ---------------------------------------------------------------------------
# Main transformation
# ---------------------------------------------------------------------------

def main() -> None:
    """Execute the complete payment transformation."""

    logger.info(
        "Starting Olist order payments dataset transformation."
    )

    # -----------------------------------------------------------------------
    # Validate input files
    # -----------------------------------------------------------------------

    validate_file_exists(
        SOURCE_FILE,
        "Payment source file",
    )

    validate_file_exists(
        ORDERS_FILE,
        "Transformed orders reference file",
    )

    # -----------------------------------------------------------------------
    # Read source
    # -----------------------------------------------------------------------

    logger.info(
        "Reading source file: %s",
        SOURCE_FILE,
    )

    payments_df = pd.read_csv(SOURCE_FILE)

    logger.info(
        "Source records loaded: %s",
        f"{len(payments_df):,}",
    )

    # -----------------------------------------------------------------------
    # Read orders reference
    # -----------------------------------------------------------------------

    logger.info(
        "Reading transformed orders reference: %s",
        ORDERS_FILE,
    )

    orders_df = pd.read_csv(ORDERS_FILE)

    logger.info(
        "Orders reference records loaded: %s",
        f"{len(orders_df):,}",
    )

    # -----------------------------------------------------------------------
    # Validate source
    # -----------------------------------------------------------------------

    validate_source_schema(
        payments_df
    )

    validate_payment_keys(
        payments_df
    )

    validate_required_fields(
        payments_df
    )

    # -----------------------------------------------------------------------
    # Standardize categorical values
    # -----------------------------------------------------------------------

    payments_df = standardize_payment_type(
        payments_df
    )

    # -----------------------------------------------------------------------
    # Validate numeric values
    # -----------------------------------------------------------------------

    validate_numeric_values(
        payments_df
    )

    # -----------------------------------------------------------------------
    # Validate referential integrity
    # -----------------------------------------------------------------------

    validate_order_references(
        payments_df,
        orders_df,
    )

    # -----------------------------------------------------------------------
    # Log payment characteristics
    # -----------------------------------------------------------------------

    log_payment_statistics(
        payments_df
    )

    # -----------------------------------------------------------------------
    # Output validation
    # -----------------------------------------------------------------------

    validate_output(
        payments_df
    )

    # -----------------------------------------------------------------------
    # Write output
    # -----------------------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payments_df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    logger.info(
        "Payment transformation completed successfully."
    )

    logger.info(
        "Source records: %s",
        f"{len(payments_df):,}",
    )

    logger.info(
        "Output records: %s",
        f"{len(payments_df):,}",
    )

    logger.info(
        "Output file: %s",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()