from __future__ import annotations

import logging

import pandas as pd

from review_util.review_config import (
    SOURCE_FILE,
    TIMESTAMP_COLUMNS,
)

logger = logging.getLogger(__name__)


def parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    for column in TIMESTAMP_COLUMNS:
        result[column] = pd.to_datetime(
            result[column],
            errors="coerce",
        )

        invalid_count = result[column].isna().sum()

        if invalid_count > 0:
            raise ValueError(
                f"Invalid timestamps detected in {column}: "
                f"{invalid_count}"
            )

    logger.info("Review timestamp parsing completed.")

    return result


def calculate_simulation_offset(
    orders_df: pd.DataFrame,
) -> pd.Timedelta:
    orders_purchase = pd.to_datetime(
        orders_df["order_purchase_timestamp"],
        errors="coerce",
    )

    if orders_purchase.isna().any():
        raise ValueError(
            "Orders reference contains invalid purchase timestamps."
        )

    source_orders = pd.read_csv(
        "/app/source_data/olist_orders_dataset.csv",
        usecols=["order_purchase_timestamp"],
    )

    source_orders["order_purchase_timestamp"] = pd.to_datetime(
        source_orders["order_purchase_timestamp"],
        errors="coerce",
    )

    if source_orders["order_purchase_timestamp"].isna().any():
        raise ValueError(
            "Source orders contain invalid purchase timestamps."
        )

    source_anchor = source_orders[
        "order_purchase_timestamp"
    ].max()

    simulation_anchor = orders_purchase.max()

    offset = simulation_anchor - source_anchor

    logger.info(
        "Source order purchase anchor: %s",
        source_anchor,
    )

    logger.info(
        "Simulation order purchase anchor: %s",
        simulation_anchor,
    )

    logger.info(
        "Using orders simulation offset: %s",
        offset,
    )

    logger.info(
        "Offset in days: %.6f",
        offset.total_seconds() / 86400,
    )

    return offset


def apply_temporal_offset(
    df: pd.DataFrame,
    offset: pd.Timedelta,
) -> pd.DataFrame:
    result = df.copy()

    for column in TIMESTAMP_COLUMNS:
        result[column] = result[column] + offset

    logger.info(
        "Applied temporal offset to %d review timestamp columns.",
        len(TIMESTAMP_COLUMNS),
    )

    return result


def validate_timestamp_anchor(
    transformed_df: pd.DataFrame,
    offset: pd.Timedelta,
) -> None:
    source_df = pd.read_csv(
        SOURCE_FILE,
        usecols=TIMESTAMP_COLUMNS,
    )

    for column in TIMESTAMP_COLUMNS:
        source_ts = pd.to_datetime(
            source_df[column],
            errors="coerce",
        )

        transformed_ts = transformed_df[column]

        expected_ts = source_ts + offset

        comparison = (
            expected_ts.reset_index(drop=True)
            == transformed_ts.reset_index(drop=True)
        )

        both_null = (
            source_ts.isna()
            & transformed_ts.isna()
        )

        valid = comparison | both_null

        if not valid.all():
            invalid_count = (~valid).sum()
            raise ValueError(
                f"Temporal offset validation failed for "
                f"{column}: {invalid_count} rows."
            )

    logger.info("Temporal offset validation passed.")