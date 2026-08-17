from __future__ import annotations

import pandas as pd

from geolocation_util.geolocation_validation import (
    analyze_duplicates,
    validate_geographic_values,
    validate_output_data_types,
    validate_output_duplicates,
    validate_output_row_count,
    validate_output_schema,
    validate_required_fields,
    validate_source_schema,
    validate_states,
    validate_zip_codes,
)

def standardize_text_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize geolocation city and state fields.
    """
    df = df.copy()

    df["geolocation_city"] = (
        df["geolocation_city"]
        .astype("string")
        .str.strip()
        .str.lower()
    )

    df["geolocation_state"] = (
        df["geolocation_state"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    return df


def transform_geolocation(
    source_df: pd.DataFrame,
) -> pd.DataFrame:
    validate_source_schema(source_df)
    validate_required_fields(source_df)
    validate_zip_codes(source_df)

    analyze_duplicates(source_df)
    validate_geographic_values(source_df)

    transformed_df = standardize_text_fields(source_df)

    validate_states(transformed_df)
    validate_output_row_count(source_df, transformed_df)
    validate_output_duplicates(source_df, transformed_df)
    validate_output_schema(transformed_df)
    validate_output_data_types(transformed_df)

    return transformed_df