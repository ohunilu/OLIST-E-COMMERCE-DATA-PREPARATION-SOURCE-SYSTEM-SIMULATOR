from __future__ import annotations

import logging

import pandas as pd

from order_util.order_config import (
    EXPECTED_OUTPUT_COLUMNS,
    REQUIRED_COLUMNS,
    TIMESTAMP_COLUMNS,
)

logger = logging.getLogger(__name__)


def validate_source_schema(df: pd.DataFrame) -> None:
    """Validate that the source contains the expected columns."""
    actual_columns = set(df.columns)
    missing_columns = REQUIRED_COLUMNS - actual_columns

    if missing_columns:
        raise ValueError(
            "Source file is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    logger.info("Source schema validation passed.")


def validate_source_keys(df: pd.DataFrame) -> None:
    """Validate order and customer identifiers."""
    if df["order_id"].isna().any():
        raise ValueError("order_id contains NULL values.")

    if df["customer_id"].isna().any():
        raise ValueError("customer_id contains NULL values.")

    duplicate_order_ids = df["order_id"].duplicated().sum()

    if duplicate_order_ids > 0:
        raise ValueError(
            f"Found {duplicate_order_ids} duplicate order_id values."
        )

    logger.info("Order key validation passed.")


def validate_purchase_timestamps(df: pd.DataFrame) -> None:
    """Ensure every order has a valid purchase timestamp."""
    missing_purchase_dates = df["order_purchase_timestamp"].isna().sum()

    if missing_purchase_dates > 0:
        raise ValueError(
            "Found "
            f"{missing_purchase_dates:,} orders with invalid or missing "
            "order_purchase_timestamp."
        )

    logger.info("Purchase timestamp validation passed.")


def validate_event_chronology(df: pd.DataFrame) -> dict[str, int]:
    """
    Profile order lifecycle chronology.

    Chronology violations that already exist in the source are treated
    as source data-quality anomalies rather than transformation failures.
    """

    chronology_rules = [
        (
            "order_purchase_timestamp",
            "order_approved_at",
            "purchase <= approved",
        ),
        (
            "order_approved_at",
            "order_delivered_carrier_date",
            "approved <= carrier",
        ),
        (
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "carrier <= delivered",
        ),
        (
            "order_purchase_timestamp",
            "order_estimated_delivery_date",
            "purchase <= estimated_delivery",
        ),
    ]

    anomaly_counts = {}

    for earlier_column, later_column, description in chronology_rules:
        mask = (
            df[earlier_column].notna()
            & df[later_column].notna()
            & (df[earlier_column] > df[later_column])
        )

        violations = int(mask.sum())
        anomaly_counts[description] = violations

        if violations > 0:
            logger.warning(
                "Source chronology anomaly: %s | rows=%s",
                description,
                f"{violations:,}",
            )
        else:
            logger.info(
                "Chronology check passed: %s",
                description,
            )

    total_anomalies = sum(anomaly_counts.values())

    if total_anomalies > 0:
        logger.warning(
            "Total source chronology anomalies preserved: %s",
            f"{total_anomalies:,}",
        )
    else:
        logger.info(
            "No source chronology anomalies detected."
        )

    return anomaly_counts


def validate_temporal_anchor(
    df: pd.DataFrame,
    expected_anchor: pd.Timestamp,
) -> None:
    """Confirm that the latest simulated purchase timestamp equals the configured simulation reference timestamp."""
    actual_anchor = df["order_purchase_timestamp"].max()

    if actual_anchor != expected_anchor:
        raise ValueError(
            "Simulation anchor validation failed. "
            f"Expected {expected_anchor}, got {actual_anchor}."
        )

    logger.info(
        "Simulation anchor validation passed: %s",
        actual_anchor,
    )


def validate_null_preservation(
    source_df: pd.DataFrame,
    transformed_df: pd.DataFrame,
) -> None:
    """Ensure that timestamp NULLs were not converted into artificial dates."""
    for column in TIMESTAMP_COLUMNS:
        source_nulls = int(source_df[column].isna().sum())
        transformed_nulls = int(transformed_df[column].isna().sum())

        if source_nulls != transformed_nulls:
            raise ValueError(
                f"NULL preservation failed for {column}. "
                f"Source NULLs={source_nulls}, "
                f"Transformed NULLs={transformed_nulls}."
            )

    logger.info(
        "Timestamp NULL preservation validation passed."
    )


def validate_output(df: pd.DataFrame) -> None:
    """Validate the final transformed orders dataset."""
    if list(df.columns) != EXPECTED_OUTPUT_COLUMNS:
        raise ValueError(
            "Output schema does not match expected schema.\n"
            f"Expected: {EXPECTED_OUTPUT_COLUMNS}\n"
            f"Actual:   {list(df.columns)}"
        )

    if df["order_id"].isna().any():
        raise ValueError(
            "Transformed order_id contains NULL values."
        )

    if df["customer_id"].isna().any():
        raise ValueError(
            "Transformed customer_id contains NULL values."
        )

    if df["order_id"].duplicated().any():
        raise ValueError(
            "Transformed order_id contains duplicate values."
        )

    if df["order_purchase_timestamp"].isna().any():
        raise ValueError(
            "Transformed order_purchase_timestamp contains NULL values."
        )

    logger.info("Output schema validation passed.")