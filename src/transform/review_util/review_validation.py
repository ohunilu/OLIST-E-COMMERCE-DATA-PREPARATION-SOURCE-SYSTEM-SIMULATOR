from __future__ import annotations

import logging

import pandas as pd

from review_util.review_config import (
    EXPECTED_OUTPUT_COLUMNS,
    EXPECTED_SOURCE_COLUMNS,
    ORDERS_REQUIRED_COLUMNS,
    TIMESTAMP_COLUMNS,
)

logger = logging.getLogger(__name__)


def validate_source_schema(df: pd.DataFrame) -> None:
    actual_columns = list(df.columns)

    missing_columns = [
        column
        for column in EXPECTED_SOURCE_COLUMNS
        if column not in actual_columns
    ]

    unexpected_columns = [
        column
        for column in actual_columns
        if column not in EXPECTED_SOURCE_COLUMNS
    ]

    if missing_columns:
        raise ValueError(
            "Source dataset is missing required columns: "
            f"{missing_columns}"
        )

    if unexpected_columns:
        logger.warning(
            "Source dataset contains unexpected columns: %s",
            unexpected_columns,
        )

    logger.info("Source schema validation passed.")


def validate_orders_schema(df: pd.DataFrame) -> None:
    missing_columns = [
        column
        for column in ORDERS_REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Orders reference is missing required columns: "
            f"{missing_columns}"
        )

    logger.info("Orders reference schema validation passed.")


def validate_review_key(df: pd.DataFrame) -> None:
    duplicate_count = df.duplicated(
        subset=["review_id", "order_id"]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            "Duplicate review_id + order_id keys detected: "
            f"{duplicate_count}"
        )

    logger.info("Composite review key validation passed.")


def validate_required_fields(df: pd.DataFrame) -> None:
    required_columns = [
        "review_id",
        "order_id",
        "review_score",
        "review_creation_date",
        "review_answer_timestamp",
    ]

    null_counts = df[required_columns].isna().sum()

    invalid = null_counts[null_counts > 0]

    if not invalid.empty:
        raise ValueError(
            "Required fields contain NULL values: "
            f"{invalid.to_dict()}"
        )

    logger.info("Required field validation passed.")


def validate_review_scores(df: pd.DataFrame) -> None:
    invalid_scores = ~df["review_score"].isin([1, 2, 3, 4, 5])

    invalid_count = invalid_scores.sum()

    if invalid_count > 0:
        raise ValueError(
            f"Invalid review scores detected: {invalid_count}"
        )

    logger.info("Review score validation passed.")


def validate_review_chronology(df: pd.DataFrame) -> None:
    invalid = (
        df["review_creation_date"]
        > df["review_answer_timestamp"]
    )

    invalid_count = invalid.sum()

    if invalid_count > 0:
        logger.warning(
            "Source chronology anomaly: "
            "review_creation_date <= review_answer_timestamp | "
            "rows=%d",
            invalid_count,
        )
        logger.warning(
            "Review chronology anomalies preserved from source."
        )
    else:
        logger.info(
            "Review chronology check passed: creation <= answer"
        )


def validate_order_reference(
    reviews_df: pd.DataFrame,
    orders_df: pd.DataFrame,
) -> None:
    review_orders = set(
        reviews_df["order_id"].dropna().unique()
    )

    transformed_orders = set(
        orders_df["order_id"].dropna().unique()
    )

    missing_orders = review_orders - transformed_orders

    if missing_orders:
        logger.warning(
            "Reviews reference %d order IDs not present in transformed orders.",
            len(missing_orders),
        )
        logger.warning(
            "These source-system reference anomalies will be preserved."
        )
    else:
        logger.info("Order reference validation passed.")


def validate_output_schema(df: pd.DataFrame) -> None:
    actual_columns = list(df.columns)

    if actual_columns != EXPECTED_OUTPUT_COLUMNS:
        raise ValueError(
            "Output schema mismatch.\n"
            f"Expected: {EXPECTED_OUTPUT_COLUMNS}\n"
            f"Actual:   {actual_columns}"
        )

    logger.info("Output schema validation passed.")


def validate_output_row_count(
    source_df: pd.DataFrame,
    transformed_df: pd.DataFrame,
) -> None:
    if len(source_df) != len(transformed_df):
        raise ValueError(
            "Output row count does not match source.\n"
            f"Source: {len(source_df)}\n"
            f"Output: {len(transformed_df)}"
        )

    logger.info(
        "Output row-count validation passed: %d records.",
        len(transformed_df),
    )


def validate_output_key(df: pd.DataFrame) -> None:
    duplicate_count = df.duplicated(
        subset=["review_id", "order_id"]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            "Output contains duplicate review_id + order_id keys: "
            f"{duplicate_count}"
        )

    logger.info("Output review key validation passed.")


def validate_timestamp_null_preservation(
    source_df: pd.DataFrame,
    transformed_df: pd.DataFrame,
) -> None:
    for column in TIMESTAMP_COLUMNS:
        source_nulls = source_df[column].isna().sum()
        transformed_nulls = transformed_df[column].isna().sum()

        if source_nulls != transformed_nulls:
            raise ValueError(
                f"Timestamp NULL preservation failed for {column}: "
                f"source={source_nulls}, "
                f"output={transformed_nulls}"
            )

    logger.info("Timestamp NULL preservation validation passed.")