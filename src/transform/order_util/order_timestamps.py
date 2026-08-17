from __future__ import annotations

import logging

import pandas as pd

from order_util.order_config import SIMULATION_AS_OF, TIMESTAMP_COLUMNS

logger = logging.getLogger(__name__)


def parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert all order lifecycle timestamp columns to pandas datetime.

    Invalid timestamps are converted to NaT.
    """
    result = df.copy()

    for column in TIMESTAMP_COLUMNS:
        result[column] = pd.to_datetime(
            result[column],
            errors="coerce",
        )

    logger.info("Timestamp parsing completed.")

    return result


def calculate_simulation_offset(
    df: pd.DataFrame,
) -> tuple[pd.Timedelta, pd.Timestamp]:
    """
    Calculate the deterministic temporal offset.

    The latest source purchase timestamp becomes SIMULATION_AS_OF.
    """
    source_anchor = df["order_purchase_timestamp"].max()

    if pd.isna(source_anchor):
        raise ValueError(
            "Unable to calculate simulation anchor. "
            "No valid purchase timestamps were found."
        )

    offset = SIMULATION_AS_OF - source_anchor

    logger.info(
        "Source purchase anchor: %s",
        source_anchor,
    )

    logger.info(
        "Simulation as-of: %s",
        SIMULATION_AS_OF,
    )

    logger.info(
        "Calculated simulation offset: %s",
        offset,
    )

    logger.info(
        "Offset in days: %.6f",
        offset.total_seconds() / 86400,
    )

    return offset, source_anchor


def shift_timestamps(
    df: pd.DataFrame,
    offset: pd.Timedelta,
) -> pd.DataFrame:
    """
    Apply the same temporal offset to every non-null lifecycle timestamp.
    NULL timestamps remain NULL.
    """
    result = df.copy()

    for column in TIMESTAMP_COLUMNS:
        result[column] = result[column] + offset

    logger.info(
        "Applied identical temporal offset to %d timestamp columns.",
        len(TIMESTAMP_COLUMNS),
    )

    return result


def standardize_order_status(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize order status values."""
    result = df.copy()

    result["order_status"] = (
        result["order_status"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    logger.info(
        "Order status standardization completed."
    )

    logger.info(
        "Order statuses found: %s",
        sorted(result["order_status"].dropna().unique().tolist()),
    )

    return result