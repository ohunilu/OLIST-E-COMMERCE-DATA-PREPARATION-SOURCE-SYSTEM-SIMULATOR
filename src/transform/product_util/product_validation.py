from __future__ import annotations

import logging

import pandas as pd

from product_util.product_config import (
    EXPECTED_OUTPUT_COLUMNS,
    EXPECTED_SOURCE_COLUMNS,
    EXPECTED_TRANSLATION_COLUMNS,
)

logger = logging.getLogger(__name__)


def validate_source_schema(df: pd.DataFrame) -> None:
    missing_columns = [
        column
        for column in EXPECTED_SOURCE_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Source schema validation failed. "
            f"Missing columns: {missing_columns}"
        )

    logger.info("Source schema validation passed.")


def validate_translation_schema(
    translation_df: pd.DataFrame,
) -> None:
    missing_columns = [
        column
        for column in EXPECTED_TRANSLATION_COLUMNS
        if column not in translation_df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Translation schema validation failed. "
            f"Missing columns: {missing_columns}"
        )

    logger.info("Translation schema validation passed.")


def validate_product_keys(df: pd.DataFrame) -> None:
    null_product_ids = df["product_id"].isna().sum()

    if null_product_ids > 0:
        raise ValueError(
            "Product key validation failed. "
            f"NULL product_id values: {null_product_ids}"
        )

    duplicate_product_ids = df["product_id"].duplicated().sum()

    if duplicate_product_ids > 0:
        raise ValueError(
            "Product key validation failed. "
            f"Duplicate product_id values: {duplicate_product_ids}"
        )

    logger.info("Product key validation passed.")


def validate_translation_keys(
    translation_df: pd.DataFrame,
) -> None:
    null_keys = translation_df["product_category_name"].isna().sum()

    if null_keys > 0:
        raise ValueError(
            "Translation key validation failed. "
            f"NULL Portuguese category keys: {null_keys}"
        )

    duplicate_keys = translation_df["product_category_name"].duplicated().sum()

    if duplicate_keys > 0:
        raise ValueError(
            "Translation key validation failed. "
            f"Duplicate Portuguese category keys: {duplicate_keys}"
        )

    null_translations = translation_df[
        "product_category_name_english"
    ].isna().sum()

    if null_translations > 0:
        raise ValueError(
            "Translation value validation failed. "
            f"NULL English category values: {null_translations}"
        )

    duplicate_translations = translation_df[
        "product_category_name_english"
    ].duplicated().sum()

    if duplicate_translations > 0:
        logger.warning(
            "Translation reference contains %s duplicate "
            "English category values. This is informational only.",
            duplicate_translations,
        )

    logger.info("Translation key validation passed.")


def validate_required_fields(df: pd.DataFrame) -> None:
    required_columns = ["product_id"]

    null_counts = df[required_columns].isna().sum()

    invalid = {
        column: int(count)
        for column, count in null_counts.items()
        if count > 0
    }

    if invalid:
        raise ValueError(
            "Required field validation failed: "
            f"{invalid}"
        )

    logger.info("Required field validation passed.")


def validate_numeric_values(df: pd.DataFrame) -> None:
    numeric_columns = [
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]

    for column in numeric_columns:
        if not pd.api.types.is_numeric_dtype(df[column]):
            raise ValueError(
                f"Numeric validation failed. "
                f"Column '{column}' is not numeric."
            )

    non_negative_columns = [
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]

    negative_counts = {}

    for column in non_negative_columns:
        count = (df[column].dropna() < 0).sum()

        if count > 0:
            negative_counts[column] = int(count)

    if negative_counts:
        raise ValueError(
            "Numeric value validation failed. "
            f"Negative values found: {negative_counts}"
        )

    logger.info("Numeric value validation passed.")


def validate_output_schema(df: pd.DataFrame) -> None:
    actual_columns = list(df.columns)

    if actual_columns != EXPECTED_OUTPUT_COLUMNS:
        missing_columns = [
            column
            for column in EXPECTED_OUTPUT_COLUMNS
            if column not in actual_columns
        ]

        unexpected_columns = [
            column
            for column in actual_columns
            if column not in EXPECTED_OUTPUT_COLUMNS
        ]

        raise ValueError(
            "Output schema validation failed. "
            f"Missing columns: {missing_columns}; "
            f"Unexpected columns: {unexpected_columns}"
        )

    logger.info("Output schema validation passed.")


def validate_output_row_count(
    source_df: pd.DataFrame,
    output_df: pd.DataFrame,
) -> None:
    if len(source_df) != len(output_df):
        raise ValueError(
            "Output row-count validation failed. "
            f"Source: {len(source_df):,}; "
            f"Output: {len(output_df):,}"
        )

    logger.info(
        "Output row-count validation passed: %s records.",
        f"{len(output_df):,}",
    )


def validate_output_keys(df: pd.DataFrame) -> None:
    null_product_ids = df["product_id"].isna().sum()

    if null_product_ids > 0:
        raise ValueError(
            "Output key validation failed. "
            f"NULL product_id values: {null_product_ids}"
        )

    duplicate_product_ids = df["product_id"].duplicated().sum()

    if duplicate_product_ids > 0:
        raise ValueError(
            "Output key validation failed. "
            f"Duplicate product_id values: {duplicate_product_ids}"
        )

    logger.info("Output product key validation passed.")