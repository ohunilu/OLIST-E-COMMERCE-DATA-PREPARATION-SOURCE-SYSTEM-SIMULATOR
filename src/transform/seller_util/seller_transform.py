from __future__ import annotations

import logging

import pandas as pd

from seller_util.seller_validation import (
    validate_numeric_values,
    validate_required_fields,
    validate_seller_keys,
    validate_source_schema,
    validate_state_values,
)

logger = logging.getLogger(__name__)


def standardize_text_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize textual seller attributes.
    """
    df = df.copy()

    df["seller_id"] = (
        df["seller_id"]
        .astype(str)
        .str.strip()
    )

    df["seller_city"] = (
        df["seller_city"]
        .astype(str)
        .str.strip()
    )

    df["seller_state"] = (
        df["seller_state"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    logger.info("Seller text standardization completed.")

    return df


def transform_sellers(df: pd.DataFrame) -> pd.DataFrame:
    validate_source_schema(df)
    validate_seller_keys(df)
    validate_required_fields(df)
    validate_numeric_values(df)

    standardized_df = standardize_text_fields(df)

    validate_state_values(standardized_df)

    return standardized_df