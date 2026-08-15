from __future__ import annotations

import pandas as pd

from product_util.product_category import (
    translate_product_categories,
)
from product_util.product_validation import (
    validate_numeric_values,
    validate_product_keys,
    validate_required_fields,
    validate_source_schema,
    validate_translation_keys,
    validate_translation_schema,
)

def transform_products(
    source_df: pd.DataFrame,
    translation_df: pd.DataFrame,
) -> pd.DataFrame:
    validate_source_schema(source_df)
    validate_translation_schema(translation_df)
    validate_product_keys(source_df)
    validate_translation_keys(translation_df)
    validate_required_fields(source_df)
    validate_numeric_values(source_df)

    transformed_df = translate_product_categories(
        source_df,
        translation_df,
    )

    return transformed_df