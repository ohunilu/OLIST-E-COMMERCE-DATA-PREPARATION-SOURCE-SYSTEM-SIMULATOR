"""
Transform Olist order reviews dataset into simulated source-system data.

Source:
    /app/source_data/olist_order_reviews_dataset.csv

Reference:
    /app/simulated_data/orders.csv

Output:
    /app/simulated_data/reviews.csv

Purpose:
    - Preserve the Olist review dataset structure and business semantics.
    - Apply the same temporal simulation offset used by orders.csv.
    - Preserve duplicate review_id values because review_id alone is not unique
      in the source dataset.
    - Validate the composite review_id + order_id key.
    - Preserve NULL review title/message values.
    - Validate review scores and timestamps.
    - Validate that all referenced orders exist in the transformed orders dataset.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from review_util.review_config import (
    ORDERS_REFERENCE_FILE,
    OUTPUT_FILE,
    SOURCE_FILE,
    TIMESTAMP_COLUMNS,
)
from review_util.review_io import (
    read_orders_reference as _read_orders_reference,
    read_source_data as _read_source_data,
    validate_file_exists as _validate_file_exists,
    write_output as _write_output,
)
from review_util.review_temporal import (
    apply_temporal_offset as _apply_temporal_offset,
    calculate_simulation_offset as _calculate_simulation_offset,
    parse_timestamps as _parse_timestamps,
    validate_timestamp_anchor as _validate_timestamp_anchor,
)
from review_util.review_transform import (
    transform_reviews as _transform_reviews,
)
from review_util.review_validation import (
    validate_order_reference as _validate_order_reference,
    validate_output_key as _validate_output_key,
    validate_output_row_count as _validate_output_row_count,
    validate_output_schema as _validate_output_schema,
    validate_required_fields as _validate_required_fields,
    validate_review_chronology as _validate_review_chronology,
    validate_review_key as _validate_review_key,
    validate_review_scores as _validate_review_scores,
    validate_source_schema as _validate_source_schema,
    validate_orders_schema as _validate_orders_schema,
    validate_timestamp_null_preservation as _validate_timestamp_null_preservation,
)

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

# Utility functions
def validate_file_exists(path: Path, description: str) -> None:
    _validate_file_exists(path, description)


def validate_source_schema(df: pd.DataFrame) -> None:
    _validate_source_schema(df)


def validate_orders_schema(df: pd.DataFrame) -> None:
    _validate_orders_schema(df)


def validate_review_key(df: pd.DataFrame) -> None:
    _validate_review_key(df)


def validate_required_fields(df: pd.DataFrame) -> None:
    _validate_required_fields(df)


def parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    return _parse_timestamps(df)


def validate_review_scores(df: pd.DataFrame) -> None:
    _validate_review_scores(df)


def validate_review_chronology(df: pd.DataFrame) -> None:
    _validate_review_chronology(df)


def calculate_simulation_offset(
    orders_df: pd.DataFrame,
) -> pd.Timedelta:
    return _calculate_simulation_offset(orders_df)


def apply_temporal_offset(
    df: pd.DataFrame,
    offset: pd.Timedelta,
) -> pd.DataFrame:
    return _apply_temporal_offset(df, offset)


def validate_order_reference(
    reviews_df: pd.DataFrame,
    orders_df: pd.DataFrame,
) -> None:
    _validate_order_reference(reviews_df, orders_df)


def validate_timestamp_anchor(
    transformed_df: pd.DataFrame,
    offset: pd.Timedelta,
) -> None:
    _validate_timestamp_anchor(transformed_df, offset)


def validate_timestamp_null_preservation(
    source_df: pd.DataFrame,
    transformed_df: pd.DataFrame,
) -> None:
    _validate_timestamp_null_preservation(
        source_df,
        transformed_df,
    )


def validate_output_schema(df: pd.DataFrame) -> None:
    _validate_output_schema(df)


def validate_output_row_count(
    source_df: pd.DataFrame,
    transformed_df: pd.DataFrame,
) -> None:
    _validate_output_row_count(source_df, transformed_df)


def validate_output_key(df: pd.DataFrame) -> None:
    _validate_output_key(df)

# Main transformation
def main() -> None:
    logger.info(
        "Starting Olist order reviews dataset transformation."
    )

    validate_file_exists(
        SOURCE_FILE,
        "Review source file",
    )

    validate_file_exists(
        ORDERS_REFERENCE_FILE,
        "Transformed orders reference",
    )

    logger.info(
        "Reading source file: %s",
        SOURCE_FILE,
    )

    source_df = _read_source_data()

    logger.info(
        "Source records loaded: %s",
        f"{len(source_df):,}",
    )

    logger.info(
        "Reading transformed orders reference: %s",
        ORDERS_REFERENCE_FILE,
    )

    orders_df = _read_orders_reference()

    logger.info(
        "Orders reference records loaded: %s",
        f"{len(orders_df):,}",
    )

    validate_source_schema(source_df)
    validate_orders_schema(orders_df)
    validate_review_key(source_df)
    validate_required_fields(source_df)

    source_df = parse_timestamps(source_df)

    validate_review_scores(source_df)

    logger.info(
        "Review score distribution: %s",
        source_df["review_score"]
        .value_counts()
        .sort_index()
        .to_dict(),
    )

    validate_review_chronology(source_df)

    simulation_offset = calculate_simulation_offset(
        orders_df
    )

    transformed_df = _transform_reviews(
        source_df,
        orders_df,
    )

    validate_order_reference(
        transformed_df,
        orders_df,
    )

    validate_output_row_count(
        source_df,
        transformed_df,
    )

    validate_output_key(
        transformed_df,
    )

    transformed_df = transformed_df[
        [
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ]
    ]

    validate_output_schema(
        transformed_df,
    )

    _write_output(transformed_df)

    logger.info(
        "Output file written: %s",
        OUTPUT_FILE,
    )

    logger.info(
        "Review transformation completed successfully."
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
        "Source review creation range: %s to %s",
        source_df["review_creation_date"].min(),
        source_df["review_creation_date"].max(),
    )

    logger.info(
        "Simulation review creation range: %s to %s",
        transformed_df["review_creation_date"].min(),
        transformed_df["review_creation_date"].max(),
    )

    logger.info(
        "Simulation offset: %s",
        simulation_offset,
    )

    logger.info(
        "Output file: %s",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()