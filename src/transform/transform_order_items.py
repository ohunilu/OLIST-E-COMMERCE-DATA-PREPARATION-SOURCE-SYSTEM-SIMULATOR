from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from order_item_util.order_item_config import (
    OUTPUT_FILE,
    SOURCE_FILE,
)
from order_item_util.order_item_temporal import (
    apply_temporal_shift as _apply_temporal_shift,
    calculate_orders_offset as _calculate_orders_offset,
)
from order_item_util.order_item_transform import (
    transform_order_items as _transform_order_items,
)
from order_item_util.order_item_validation import (
    validate_numeric_values as _validate_numeric_values,
    validate_order_item_keys as _validate_order_item_keys,
    validate_output as _validate_output,
    validate_required_fields as _validate_required_fields,
    validate_source_schema as _validate_source_schema,
)

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

# Source Validation
def validate_source_schema(df: pd.DataFrame) -> None:
    _validate_source_schema(df)


def validate_order_item_keys(df: pd.DataFrame) -> None:
    _validate_order_item_keys(df)


def validate_required_fields(df: pd.DataFrame) -> None:
    _validate_required_fields(df)


# Business Validation
def validate_numeric_values(df: pd.DataFrame) -> None:
    _validate_numeric_values(df)


# Temporal Simulation
def calculate_orders_offset() -> pd.Timedelta:
    return _calculate_orders_offset()


def apply_temporal_shift(
    df: pd.DataFrame,
    offset: pd.Timedelta,
) -> pd.DataFrame:
    return _apply_temporal_shift(df, offset)


# Output Validation
def validate_output(df: pd.DataFrame) -> None:
    _validate_output(df)


# Transformation
def transform_order_items(
    source_df: pd.DataFrame,
) -> pd.DataFrame:
    return _transform_order_items(source_df)


# Main
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