from __future__ import annotations

import logging

import pandas as pd

from order_item_util.order_item_config import (
    ORDERS_SOURCE_FILE,
    SIMULATION_AS_OF,
)

logger = logging.getLogger(__name__)


def calculate_orders_offset() -> pd.Timedelta:
    """
    Calculate the same temporal offset used by transform_orders.py.
    """
    orders = pd.read_csv(
        ORDERS_SOURCE_FILE,
        usecols=["order_purchase_timestamp"],
    )

    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"],
        errors="coerce",
    )

    source_anchor = orders["order_purchase_timestamp"].max()

    offset = SIMULATION_AS_OF - source_anchor

    logger.info(
        "Using orders simulation offset: %s",
        offset,
    )

    return offset


def apply_temporal_shift(
    df: pd.DataFrame,
    offset: pd.Timedelta,
) -> pd.DataFrame:
    result = df.copy()

    result["shipping_limit_date"] = pd.to_datetime(
        result["shipping_limit_date"],
        errors="coerce",
    )

    result["shipping_limit_date"] = (
        result["shipping_limit_date"] + offset
    )

    logger.info(
        "Applied temporal offset to shipping_limit_date."
    )

    return result