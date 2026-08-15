from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def normalize_category_values(
    df: pd.DataFrame,
    translation_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    translation_df = translation_df.copy()

    df["product_category_name"] = (
        df["product_category_name"]
        .astype("string")
        .str.strip()
    )

    translation_df["product_category_name"] = (
        translation_df["product_category_name"]
        .astype("string")
        .str.strip()
    )

    translation_df["product_category_name_english"] = (
        translation_df["product_category_name_english"]
        .astype("string")
        .str.strip()
    )

    return df, translation_df


def translate_product_categories(
    df: pd.DataFrame,
    translation_df: pd.DataFrame,
) -> pd.DataFrame:
    source_row_count = len(df)

    logger.info(
        "Starting product category translation enrichment."
    )

    df, translation_df = normalize_category_values(
        df,
        translation_df,
    )

    df["_source_product_category_name"] = (
        df["product_category_name"]
    )

    translation_lookup = translation_df[
        [
            "product_category_name",
            "product_category_name_english",
        ]
    ].copy()

    enriched_df = df.merge(
        translation_lookup,
        on="product_category_name",
        how="left",
        validate="many_to_one",
    )

    if len(enriched_df) != source_row_count:
        raise ValueError(
            "Translation enrichment changed the product row count. "
            f"Before: {source_row_count:,}; "
            f"After: {len(enriched_df):,}"
        )

    logger.info(
        "Translation enrichment row-count validation passed."
    )

    source_categories = (
        df["_source_product_category_name"]
        .dropna()
        .nunique()
    )

    translated_categories = (
        enriched_df.loc[
            enriched_df["_source_product_category_name"].notna()
            & enriched_df["product_category_name_english"].notna(),
            "_source_product_category_name",
        ]
        .nunique()
    )

    unmatched_categories = (
        enriched_df.loc[
            enriched_df["_source_product_category_name"].notna()
            & enriched_df["product_category_name_english"].isna(),
            "_source_product_category_name",
        ]
        .nunique()
    )

    null_source_categories = (
        enriched_df["_source_product_category_name"].isna().sum()
    )

    logger.info(
        "Source categories found: %s",
        f"{source_categories:,}",
    )

    logger.info(
        "Categories successfully translated: %s",
        f"{translated_categories:,}",
    )

    logger.info(
        "Categories without translation mapping: %s",
        f"{unmatched_categories:,}",
    )

    logger.info(
        "Products with NULL source category: %s",
        f"{null_source_categories:,}",
    )

    if unmatched_categories > 0:
        logger.warning(
            "Some source categories do not have an English "
            "translation. They will remain NULL."
        )

    enriched_df["product_category_name"] = (
        enriched_df["product_category_name_english"]
    )

    enriched_df.drop(
        columns=[
            "_source_product_category_name",
            "product_category_name_english",
        ],
        inplace=True,
    )

    logger.info(
        "Product category replacement completed."
    )

    return enriched_df