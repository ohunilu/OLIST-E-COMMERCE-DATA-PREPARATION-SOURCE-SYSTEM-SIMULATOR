"""
Transform Olist products dataset into a simulated production product catalog.

Source:
    /app/source_data/olist_products_dataset.csv

Reference:
    /app/source_data/product_category_name_translation.csv

Output:
    /app/simulated_data/products.csv

Transformation responsibilities:
    1. Validate the source product schema.
    2. Validate product_id uniqueness.
    3. Validate the category translation reference.
    4. Translate Portuguese product categories to English.
    5. Preserve NULL source categories where no category exists.
    6. Preserve unmatched categories as NULL rather than inventing values.
    7. Preserve product-level attributes.
    8. Validate row-count preservation after enrichment.
    9. Validate output schema and key integrity.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_FILE = Path(
    "/app/source_data/olist_products_dataset.csv"
)

TRANSLATION_FILE = Path(
    "/app/source_data/product_category_name_translation.csv"
)

OUTPUT_FILE = Path(
    "/app/simulated_data/products.csv"
)


EXPECTED_SOURCE_COLUMNS = [
    "product_id",
    "product_category_name",
    "product_name_lenght",
    "product_description_lenght",
    "product_photos_qty",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
]


EXPECTED_TRANSLATION_COLUMNS = [
    "product_category_name",
    "product_category_name_english",
]


EXPECTED_OUTPUT_COLUMNS = [
    "product_id",
    "product_category_name",
    "product_name_lenght",
    "product_description_lenght",
    "product_photos_qty",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------

def load_source_data() -> pd.DataFrame:
    """Load the Olist products dataset."""

    logger.info("Reading source file: %s", SOURCE_FILE)

    if not SOURCE_FILE.exists():
        raise FileNotFoundError(
            f"Source file not found: {SOURCE_FILE}"
        )

    df = pd.read_csv(SOURCE_FILE)

    logger.info("Source records loaded: %s", f"{len(df):,}")

    return df


def load_translation_data() -> pd.DataFrame:
    """Load the product category translation reference."""

    logger.info("Reading translation reference: %s", TRANSLATION_FILE)

    if not TRANSLATION_FILE.exists():
        raise FileNotFoundError(
            f"Translation file not found: {TRANSLATION_FILE}"
        )

    translation_df = pd.read_csv(TRANSLATION_FILE)

    logger.info(
        "Translation records loaded: %s",
        f"{len(translation_df):,}",
    )

    return translation_df


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def validate_source_schema(df: pd.DataFrame) -> None:
    """Validate the expected source columns."""

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
    """Validate the translation reference schema."""

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


# ---------------------------------------------------------------------------
# Key validation
# ---------------------------------------------------------------------------

def validate_product_keys(df: pd.DataFrame) -> None:
    """Validate product_id integrity."""

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
    """Validate translation lookup-key integrity."""

    null_keys = translation_df[
        "product_category_name"
    ].isna().sum()

    if null_keys > 0:
        raise ValueError(
            "Translation key validation failed. "
            f"NULL Portuguese category keys: {null_keys}"
        )

    duplicate_keys = translation_df[
        "product_category_name"
    ].duplicated().sum()

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


# ---------------------------------------------------------------------------
# Data quality validation
# ---------------------------------------------------------------------------

def validate_required_fields(df: pd.DataFrame) -> None:
    """Validate fields that must always contain values."""

    required_columns = [
        "product_id",
    ]

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
    """Validate product numeric attributes."""

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


# ---------------------------------------------------------------------------
# Category translation
# ---------------------------------------------------------------------------

def normalize_category_values(
    df: pd.DataFrame,
    translation_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Normalize category lookup values before joining.

    The normalization is intentionally conservative:
        - Cast to pandas string representation.
        - Trim leading/trailing whitespace.
        - Preserve NULL values.
    """

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
    """
    Replace Portuguese category names with English category names.

    A LEFT JOIN is deliberately used so every source product remains
    represented in the output.
    """

    source_row_count = len(df)

    logger.info(
        "Starting product category translation enrichment."
    )

    df, translation_df = normalize_category_values(
        df,
        translation_df,
    )

    # Preserve the original category temporarily so that we can audit
    # translation coverage after the join.
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

    # Replace the Portuguese category with the English category.
    #
    # For categories with a valid translation:
    #     Portuguese -> English
    #
    # For NULL categories:
    #     NULL -> NULL
    #
    # For unmatched categories:
    #     Portuguese -> NULL
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


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------

def validate_output_schema(df: pd.DataFrame) -> None:
    """Validate the final simulated product schema."""

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
    """Ensure transformation does not lose or create products."""

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
    """Validate product key integrity after transformation."""

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


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------

def write_output(df: pd.DataFrame) -> None:
    """Write the transformed dataset to the simulated_data directory."""

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    logger.info(
        "Output file written: %s",
        OUTPUT_FILE,
    )


# ---------------------------------------------------------------------------
# Main transformation
# ---------------------------------------------------------------------------

def main() -> None:
    """Execute the complete product transformation pipeline."""

    logger.info(
        "Starting Olist products dataset transformation."
    )

    # -----------------------------------------------------------------------
    # 1. Load source and reference data
    # -----------------------------------------------------------------------

    source_df = load_source_data()
    translation_df = load_translation_data()

    # -----------------------------------------------------------------------
    # 2. Validate source schema
    # -----------------------------------------------------------------------

    validate_source_schema(source_df)
    validate_translation_schema(translation_df)

    # -----------------------------------------------------------------------
    # 3. Validate keys
    # -----------------------------------------------------------------------

    validate_product_keys(source_df)
    validate_translation_keys(translation_df)

    # -----------------------------------------------------------------------
    # 4. Validate required fields
    # -----------------------------------------------------------------------

    validate_required_fields(source_df)

    # -----------------------------------------------------------------------
    # 5. Validate numeric attributes
    # -----------------------------------------------------------------------

    validate_numeric_values(source_df)

    # -----------------------------------------------------------------------
    # 6. Translate product categories
    # -----------------------------------------------------------------------

    transformed_df = translate_product_categories(
        source_df,
        translation_df,
    )

    # -----------------------------------------------------------------------
    # 7. Validate final output
    # -----------------------------------------------------------------------

    validate_output_row_count(
        source_df,
        transformed_df,
    )

    validate_output_keys(
        transformed_df,
    )

    validate_output_schema(
        transformed_df,
    )

    # -----------------------------------------------------------------------
    # 8. Write output
    # -----------------------------------------------------------------------

    write_output(transformed_df)

    # -----------------------------------------------------------------------
    # 9. Completion summary
    # -----------------------------------------------------------------------

    logger.info(
        "Products transformation completed successfully."
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
        "Output file: %s",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()