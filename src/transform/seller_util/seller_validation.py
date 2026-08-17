from __future__ import annotations

import logging

import pandas as pd

from seller_util.seller_config import EXPECTED_COLUMNS, VALID_STATE_LENGTH

logger = logging.getLogger(__name__)


def validate_source_schema(df: pd.DataFrame) -> None:
    """Validate the seller source schema."""
    actual_columns = list(df.columns)

    if actual_columns != EXPECTED_COLUMNS:
        raise ValueError(
            "Unexpected seller source schema.\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Actual:   {actual_columns}"
        )

    logger.info("Source schema validation passed.")


def validate_seller_keys(df: pd.DataFrame) -> None:
    """Validate seller_id as the primary key."""
    if df["seller_id"].isna().any():
        raise ValueError("seller_id contains NULL values.")

    duplicate_count = df["seller_id"].duplicated().sum()

    if duplicate_count > 0:
        raise ValueError(
            "Duplicate seller_id values detected: "
            f"{duplicate_count}"
        )

    logger.info("Seller key validation passed.")


def validate_required_fields(df: pd.DataFrame) -> None:
    """Validate required seller attributes."""
    required_columns = EXPECTED_COLUMNS

    null_counts = df[required_columns].isna().sum()

    invalid = null_counts[null_counts > 0]

    if not invalid.empty:
        raise ValueError(
            "Required seller fields contain NULL values:\n"
            f"{invalid.to_string()}"
        )

    logger.info("Required field validation passed.")


def validate_numeric_values(df: pd.DataFrame) -> None:
    """Validate seller numeric attributes."""
    if (df["seller_zip_code_prefix"] < 0).any():
        invalid_count = (df["seller_zip_code_prefix"] < 0).sum()

        raise ValueError(
            "Negative seller ZIP code prefixes detected: "
            f"{invalid_count}"
        )

    logger.info("Numeric value validation passed.")


def validate_state_values(df: pd.DataFrame) -> None:
    """Validate Brazilian state/UF codes."""
    invalid_length = df["seller_state"].str.len().ne(VALID_STATE_LENGTH)

    if invalid_length.any():
        invalid_count = invalid_length.sum()
        raise ValueError(
            "Invalid seller_state length detected: "
            f"{invalid_count}"
        )

    invalid_values = sorted(
        df.loc[
            ~df["seller_state"].str.match(r"^[A-Z]{2}$"),
            "seller_state",
        ].unique()
    )

    if invalid_values:
        raise ValueError(
            "Invalid seller_state values detected: "
            f"{invalid_values}"
        )

    logger.info("Seller state validation passed.")


def validate_output(
    df: pd.DataFrame,
    source_record_count: int,
) -> None:
    """Validate the final transformed seller dataset."""
    if len(df) != source_record_count:
        raise ValueError(
            "Output row count changed.\n"
            f"Source: {source_record_count}\n"
            f"Output: {len(df)}"
        )

    logger.info(
        "Output row-count validation passed: %s records.",
        f"{len(df):,}",
    )

    if list(df.columns) != EXPECTED_COLUMNS:
        raise ValueError(
            "Output schema does not match expected schema.\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Actual:   {list(df.columns)}"
        )

    duplicate_count = df["seller_id"].duplicated().sum()

    if duplicate_count > 0:
        raise ValueError(
            "Output contains duplicate seller_id values: "
            f"{duplicate_count}"
        )

    if df[EXPECTED_COLUMNS].isna().any().any():
        raise ValueError(
            "Output contains unexpected NULL values."
        )

    logger.info("Output seller key validation passed.")
    logger.info("Output schema validation passed.")