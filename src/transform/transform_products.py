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

from product_util.product_config import (
    OUTPUT_FILE,
)
from product_util.product_io import (
    load_source_data as _load_source_data,
    load_translation_data as _load_translation_data,
    write_output as _write_output,
)
from product_util.product_transform import (
    transform_products as _transform_products,
)
from product_util.product_validation import (
    validate_output_keys as _validate_output_keys,
    validate_output_row_count as _validate_output_row_count,
    validate_output_schema as _validate_output_schema,
)

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

# Source loading
def load_source_data():
    return _load_source_data()


def load_translation_data():
    return _load_translation_data()


# Category translation
def translate_product_categories(df, translation_df):
    return _transform_products(df, translation_df)

# Output validation
def validate_output_schema(df):
    _validate_output_schema(df)


def validate_output_row_count(source_df, output_df):
    _validate_output_row_count(source_df, output_df)


def validate_output_keys(df):
    _validate_output_keys(df)


# Output writing
def write_output(df):
    _write_output(df)

# Main transformation
def main() -> None:
    logger.info(
        "Starting Olist products dataset transformation."
    )

    source_df = load_source_data()
    translation_df = load_translation_data()

    transformed_df = translate_product_categories(
        source_df,
        translation_df,
    )

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

    write_output(transformed_df)

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