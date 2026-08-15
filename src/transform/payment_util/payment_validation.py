from __future__ import annotations

import logging

import pandas as pd

from payment_util.payment_config import (
    EXPECTED_COLUMNS,
    VALID_PAYMENT_TYPES,
)

logger = logging.getLogger(__name__)


def validate_source_schema(df: pd.DataFrame) -> None:
    actual_columns = list(df.columns)

    if actual_columns != EXPECTED_COLUMNS:
        raise ValueError(
            "Unexpected payment source schema.\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Actual:   {actual_columns}"
        )

    logger.info("Source schema validation passed.")


def validate_payment_keys(df: pd.DataFrame) -> None:
    if df["order_id"].isna().any():
        raise ValueError("order_id contains NULL values.")

    if df["payment_sequential"].isna().any():
        raise ValueError("payment_sequential contains NULL values.")

    duplicate_count = df.duplicated(
        subset=["order_id", "payment_sequential"]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            "Duplicate order-payment keys detected: "
            f"{duplicate_count}"
        )

    logger.info("Composite payment key validation passed.")


def validate_required_fields(df: pd.DataFrame) -> None:
    required_columns = EXPECTED_COLUMNS

    null_counts = df[required_columns].isna().sum()

    invalid = null_counts[null_counts > 0]

    if not invalid.empty:
        raise ValueError(
            "Required payment fields contain NULL values:\n"
            f"{invalid.to_string()}"
        )

    logger.info("Required field validation passed.")


def standardize_payment_type(df: pd.DataFrame) -> pd.DataFrame:
    standardized = df.copy()

    standardized["payment_type"] = (
        standardized["payment_type"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    unexpected_types = sorted(
        set(standardized["payment_type"].unique())
        - VALID_PAYMENT_TYPES
    )

    if unexpected_types:
        raise ValueError(
            "Unexpected payment types detected: "
            f"{unexpected_types}"
        )

    logger.info("Payment type standardization completed.")
    logger.info(
        "Payment types found: %s",
        sorted(standardized["payment_type"].unique()),
    )

    return standardized


def validate_numeric_values(df: pd.DataFrame) -> None:
    if (df["payment_sequential"] < 1).any():
        invalid_count = (df["payment_sequential"] < 1).sum()
        raise ValueError(
            "Invalid payment_sequential values detected: "
            f"{invalid_count}"
        )

    if (df["payment_installments"] < 0).any():
        invalid_count = (df["payment_installments"] < 0).sum()
        raise ValueError(
            "Negative payment_installments detected: "
            f"{invalid_count}"
        )

    if (df["payment_value"] < 0).any():
        invalid_count = (df["payment_value"] < 0).sum()
        raise ValueError(
            "Negative payment_value values detected: "
            f"{invalid_count}"
        )

    logger.info("Numeric value validation passed.")


def validate_order_references(
    payments_df: pd.DataFrame,
    orders_df: pd.DataFrame,
) -> None:
    order_ids = set(orders_df["order_id"].dropna())
    payment_order_ids = set(payments_df["order_id"].dropna())

    orphaned_orders = payment_order_ids - order_ids

    if orphaned_orders:
        logger.error(
            "Payment records reference orders missing from transformed orders dataset: %s",
            len(orphaned_orders),
        )

        sample = sorted(orphaned_orders)[:10]

        raise ValueError(
            "Referential integrity validation failed. "
            f"Missing order references: {len(orphaned_orders)}. "
            f"Sample: {sample}"
        )

    logger.info("Order reference validation passed.")


def log_payment_statistics(df: pd.DataFrame) -> None:
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

    zero_value_count = (df["payment_value"] == 0).sum()

    logger.info("Payment type distribution: %s", payment_type_counts)
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


def validate_output(df: pd.DataFrame) -> None:
    if len(df) == 0:
        raise ValueError(
            "Output payment dataset contains zero records."
        )

    if list(df.columns) != EXPECTED_COLUMNS:
        raise ValueError(
            "Output schema does not match expected schema.\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Actual:   {list(df.columns)}"
        )

    duplicate_count = df.duplicated(
        subset=["order_id", "payment_sequential"]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            "Output contains duplicate order-payment keys: "
            f"{duplicate_count}"
        )

    if df[EXPECTED_COLUMNS].isna().any().any():
        raise ValueError(
            "Output contains unexpected NULL values."
        )

    if (df["payment_value"] < 0).any():
        raise ValueError(
            "Output contains negative payment values."
        )

    logger.info("Output schema validation passed.")