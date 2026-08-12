from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_FILE = Path("/app/source_data/olist_order_items_dataset.csv")
ORDERS_SOURCE_FILE = Path("/app/source_data/olist_orders_dataset.csv")
OUTPUT_FILE = Path("/app/simulated_data/order_items.csv")

# Must match transform_orders.py
SIMULATION_AS_OF = pd.Timestamp("2026-08-12 23:59:59")

REQUIRED_COLUMNS = {
    "order_id",
    "order_item_id",
    "product_id",
    "seller_id",
    "shipping_limit_date",
    "price",
    "freight_value",
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
# Source Validation
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Business Validation
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Temporal Simulation
# ---------------------------------------------------------------------------

def calculate_orders_offset() -> pd.Timedelta:
    """
    Calculate the same temporal offset used by transform_orders.py.

    The offset is derived from the latest purchase timestamp in the
    source orders dataset so that every transactional dataset shares
    an identical simulation clock.
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


# ---------------------------------------------------------------------------
# Output Validation
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info(
        "Starting Olist order items transformation."
    )

    if not SOURCE_FILE.exists():
        raise FileNotFoundError(SOURCE_FILE)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger.info("Reading source file: %s", SOURCE_FILE)

    df = pd.read_csv(SOURCE_FILE)

    logger.info(
        "Source records loaded: %s",
        f"{len(df):,}",
    )

    validate_source_schema(df)
    validate_order_item_keys(df)
    validate_required_fields(df)
    validate_numeric_values(df)

    offset = calculate_orders_offset()

    transformed = apply_temporal_shift(df, offset)

    validate_output(transformed)

    transformed.to_csv(
        OUTPUT_FILE,
        index=False,
        date_format="%Y-%m-%d %H:%M:%S",
    )

    logger.info(
        "Order items transformation completed successfully."
    )

    logger.info(
        "Output records: %s",
        f"{len(transformed):,}",
    )

    logger.info(
        "Output file: %s",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()