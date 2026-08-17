from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from order_util.order_config import (
    OUTPUT_FILE,
    SIMULATION_AS_OF,
    SOURCE_FILE,
    TIMESTAMP_COLUMNS,
)
from order_util.order_timestamps import (
    calculate_simulation_offset as _calculate_simulation_offset,
    parse_timestamps as _parse_timestamps,
    shift_timestamps as _shift_timestamps,
    standardize_order_status as _standardize_order_status,
)
from order_util.order_validation import (
    validate_event_chronology as _validate_event_chronology,
    validate_null_preservation as _validate_null_preservation,
    validate_output as _validate_output,
    validate_purchase_timestamps as _validate_purchase_timestamps,
    validate_source_keys as _validate_source_keys,
    validate_source_schema as _validate_source_schema,
    validate_temporal_anchor as _validate_temporal_anchor,
)
from order_util.order_transform import (
    transform_orders as _transform_orders,
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


def validate_source_keys(df: pd.DataFrame) -> None:
    _validate_source_keys(df)


# Timestamp Parsing
def parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    return _parse_timestamps(df)


def validate_purchase_timestamps(df: pd.DataFrame) -> None:
    _validate_purchase_timestamps(df)


# Temporal Simulation
def calculate_simulation_offset(
    df: pd.DataFrame,
) -> tuple[pd.Timedelta, pd.Timestamp]:
    return _calculate_simulation_offset(df)


def shift_timestamps(
    df: pd.DataFrame,
    offset: pd.Timedelta,
) -> pd.DataFrame:
    return _shift_timestamps(df, offset)

# Status Standardization
def standardize_order_status(df: pd.DataFrame) -> pd.DataFrame:
    return _standardize_order_status(df)

# Chronological Validation
def validate_event_chronology(df: pd.DataFrame) -> dict[str, int]:
    return _validate_event_chronology(df)

# Temporal Integrity Validation
def validate_temporal_anchor(
    df: pd.DataFrame,
    expected_anchor: pd.Timestamp,
) -> None:
    _validate_temporal_anchor(df, expected_anchor)


def validate_null_preservation(
    source_df: pd.DataFrame,
    transformed_df: pd.DataFrame,
) -> None:
    _validate_null_preservation(source_df, transformed_df)


# Output Validation
def validate_output(df: pd.DataFrame) -> None:
    _validate_output(df)


# Transformation
def transform_orders(
    source_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Timedelta, pd.Timestamp]:
    return _transform_orders(source_df)



# Main
def main() -> None:
    logger.info(
        "Starting Olist orders dataset transformation."
    )

    if not SOURCE_FILE.exists():
        raise FileNotFoundError(
            f"Source file not found: {SOURCE_FILE}"
        )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger.info(
        "Reading source file: %s",
        SOURCE_FILE,
    )

    source_df = pd.read_csv(SOURCE_FILE)

    logger.info(
        "Source records loaded: %s",
        f"{len(source_df):,}",
    )

    validate_source_schema(source_df)
    validate_source_keys(source_df)

    transformed_df, offset, source_anchor = transform_orders(
        source_df
    )

    validate_event_chronology(transformed_df)

    validate_temporal_anchor(
        transformed_df,
        SIMULATION_AS_OF,
    )

    validate_null_preservation(
        source_df.assign(
            **{
                column: pd.to_datetime(
                    source_df[column],
                    errors="coerce",
                )
                for column in TIMESTAMP_COLUMNS
            }
        ),
        transformed_df,
    )

    validate_output(transformed_df)

    transformed_df.to_csv(
        OUTPUT_FILE,
        index=False,
        date_format="%Y-%m-%d %H:%M:%S",
    )

    logger.info(
        "Orders transformation completed successfully."
    )

    logger.info(
        "Source records: %s",
        f"{len(source_df):,}",
    )

    logger.info(
        "Output records: %s",
        f"{len(transformed_df):,}",
    )

    logger.info(
        "Source purchase anchor: %s",
        source_anchor,
    )

    logger.info(
        "Simulation anchor: %s",
        SIMULATION_AS_OF,
    )

    logger.info(
        "Simulation offset: %s",
        offset,
    )

    logger.info(
        "Output file: %s",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()