from __future__ import annotations

import logging

import pandas as pd

from order_item_util.order_item_config import REQUIRED_COLUMNS

logger = logging.getLogger(__name__)


def validate_source_schema(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    logger.info("Source schema validation passed.")


def validate_order_item_keys(df: pd.DataFrame) -> None:
    duplicates = df.duplicated(
        subset=["order_id", "order_item_id"]
    ).sum()

    if duplicates > 0:
        raise ValueError(
            f"Found {duplicates} duplicate (order_id, order_item_id) keys."
        )

    logger.info("Composite order-item key validation passed.")


def validate_required_fields(df: pd.DataFrame) -> None:
    required = [
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
    ]

    for column in required:
        nulls = df[column].isna().sum()

        if nulls > 0:
            raise ValueError(
                f"{column} contains {nulls} NULL values."
            )

    logger.info("Required field validation passed.")


def validate_numeric_values(df: pd.DataFrame) -> None:
    negative_price = (df["price"] < 0).sum()
    negative_freight = (df["freight_value"] < 0).sum()

    if negative_price > 0:
        raise ValueError(
            f"Found {negative_price} negative price values."
        )

    if negative_freight > 0:
        raise ValueError(
            f"Found {negative_freight} negative freight values."
        )

    logger.info("Numeric value validation passed.")


def validate_output(df: pd.DataFrame) -> None:
    expected = [
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
    ]

    if list(df.columns) != expected:
        raise ValueError("Output schema mismatch.")

    if df["shipping_limit_date"].isna().any():
        raise ValueError(
            "shipping_limit_date contains NULL values."
        )

    logger.info("Output schema validation passed.")