from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def validate_source_schema(df: pd.DataFrame, required_columns: set[str]) -> None:
    """Validate that the source contains the expected columns."""
    actual_columns = set(df.columns)
    missing_columns = required_columns - actual_columns

    if missing_columns:
        raise ValueError(
            f"Source file is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    logger.info("Source schema validation passed.")


def validate_customer_keys(df: pd.DataFrame) -> None:
    """Validate customer identifiers."""
    if df["customer_id"].isna().any():
        raise ValueError("customer_id contains NULL values.")

    if df["customer_unique_id"].isna().any():
        raise ValueError("customer_unique_id contains NULL values.")

    duplicate_customer_ids = df["customer_id"].duplicated().sum()

    if duplicate_customer_ids > 0:
        raise ValueError(
            f"Found {duplicate_customer_ids} duplicate customer_id values."
        )

    logger.info("Customer key validation passed.")


def validate_output(
    df: pd.DataFrame,
    expected_columns: list[str] | None = None,
) -> None:
    """Validate the transformed customer dataset."""
    if expected_columns is None:
        expected_columns = [
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

    if list(df.columns) != expected_columns:
        raise ValueError(
            "Output schema does not match expected schema.\n"
            f"Expected: {expected_columns}\n"
            f"Actual:   {list(df.columns)}"
        )

    if df["customer_id"].isna().any():
        raise ValueError("Transformed customer_id contains NULL values.")

    if df["customer_unique_id"].isna().any():
        raise ValueError(
            "Transformed customer_unique_id contains NULL values."
        )

    if df["customer_id"].duplicated().any():
        raise ValueError(
            "Transformed customer_id contains duplicate values."
        )

    if not df["email"].str.endswith("@example.test").all():
        raise ValueError(
            "Synthetic email validation failed. "
            "All generated emails must use @example.test."
        )

    if not (df["state"].str.len() == 2).all():
        raise ValueError(
            "Customer state validation failed. "
            "Expected two-character Brazilian state codes."
        )

    if not (df["zip_code_prefix"].str.len() == 5).all():
        raise ValueError(
            "Postal code validation failed. "
            "Expected five-character postal codes."
        )

    customer_mapping = (
        df.groupby("customer_unique_id")["customer_id"]
        .nunique()
    )

    if customer_mapping.empty:
        raise ValueError(
            "No customer identity mappings were found."
        )

    logger.info(
        "Persistent customer identities: %s",
        f"{customer_mapping.shape[0]:,}",
    )

    logger.info(
        "Customer records mapped to multiple customer_id values: %s",
        f"{(customer_mapping > 1).sum():,}",
    )

    logger.info("Output validation passed.")