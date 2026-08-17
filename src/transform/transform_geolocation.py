"""
Transform Olist geolocation dataset into the simulated source-system layer.

Source:
    /app/source_data/olist_geolocation_dataset.csv

Output:
    /app/simulated_data/geolocation.csv

Transformation principles:
    - Preserve source row grain.
    - Preserve exact duplicate records.
    - Preserve source geographic anomalies.
    - Standardize city and state text.
    - Validate required fields and numeric ranges.
    - No temporal simulation is applied because this dataset has no timestamps.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from geolocation_util.geolocation_config import (
    OUTPUT_FILE,
    SOURCE_FILE,
)
from geolocation_util.geolocation_io import (
    load_source_data as _load_source_data,
    write_output as _write_output,
)
from geolocation_util.geolocation_transform import (
    standardize_text_fields as _standardize_text_fields,
    transform_geolocation as _transform_geolocation,
)
from geolocation_util.geolocation_validation import (
    analyze_duplicates as _analyze_duplicates,
    validate_geographic_values as _validate_geographic_values,
    validate_output_data_types as _validate_output_data_types,
    validate_output_duplicates as _validate_output_duplicates,
    validate_output_row_count as _validate_output_row_count,
    validate_output_schema as _validate_output_schema,
    validate_required_fields as _validate_required_fields,
    validate_source_schema as _validate_source_schema,
    validate_states as _validate_states,
    validate_zip_codes as _validate_zip_codes,
)

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
    return _load_source_data()


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def validate_source_schema(df: pd.DataFrame) -> None:
    _validate_source_schema(df)


# ---------------------------------------------------------------------------
# Required-field validation
# ---------------------------------------------------------------------------

def validate_required_fields(df: pd.DataFrame) -> None:
    _validate_required_fields(df)


# ---------------------------------------------------------------------------
# ZIP code validation
# ---------------------------------------------------------------------------

def validate_zip_codes(df: pd.DataFrame) -> None:
    _validate_zip_codes(df)


# ---------------------------------------------------------------------------
# Geographic validation
# ---------------------------------------------------------------------------

def validate_geographic_values(df: pd.DataFrame) -> None:
    _validate_geographic_values(df)


# ---------------------------------------------------------------------------
# Duplicate analysis
# ---------------------------------------------------------------------------

def analyze_duplicates(df: pd.DataFrame) -> None:
    _analyze_duplicates(df)


# ---------------------------------------------------------------------------
# Text standardization
# ---------------------------------------------------------------------------

def standardize_text_fields(df: pd.DataFrame) -> pd.DataFrame:
    return _standardize_text_fields(df)


# ---------------------------------------------------------------------------
# State validation
# ---------------------------------------------------------------------------

def validate_states(df: pd.DataFrame) -> None:
    _validate_states(df)


# ---------------------------------------------------------------------------
# Output schema validation
# ---------------------------------------------------------------------------

def validate_output_schema(df: pd.DataFrame) -> None:
    _validate_output_schema(df)


# ---------------------------------------------------------------------------
# Output row-count validation
# ---------------------------------------------------------------------------

def validate_output_row_count(
    source_df: pd.DataFrame,
    output_df: pd.DataFrame,
) -> None:
    _validate_output_row_count(source_df, output_df)


# ---------------------------------------------------------------------------
# Output duplicate validation
# ---------------------------------------------------------------------------

def validate_output_duplicates(
    source_df: pd.DataFrame,
    output_df: pd.DataFrame,
) -> None:
    _validate_output_duplicates(source_df, output_df)


# ---------------------------------------------------------------------------
# Data type validation
# ---------------------------------------------------------------------------

def validate_output_data_types(df: pd.DataFrame) -> None:
    _validate_output_data_types(df)


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------

def write_output(df: pd.DataFrame) -> None:
    _write_output(df)


# ---------------------------------------------------------------------------
# Main transformation
# ---------------------------------------------------------------------------

def main() -> None:
    """Execute the complete geolocation transformation pipeline."""
    logger.info(
        "Starting Olist geolocation dataset transformation."
    )

    source_df = load_source_data()

    validate_source_schema(source_df)
    validate_required_fields(source_df)
    validate_zip_codes(source_df)

    analyze_duplicates(source_df)
    validate_geographic_values(source_df)

    transformed_df = _transform_geolocation(source_df)

    validate_output_row_count(
        source_df,
        transformed_df,
    )

    validate_output_duplicates(
        source_df,
        transformed_df,
    )

    validate_output_schema(transformed_df)
    validate_output_data_types(transformed_df)

    write_output(transformed_df)

    logger.info(
        "Geolocation transformation completed successfully."
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
        "Unique ZIP prefixes: %s",
        f"{transformed_df['geolocation_zip_code_prefix'].nunique():,}",
    )

    logger.info(
        "Exact duplicate records preserved: %s",
        f"{transformed_df.duplicated().sum():,}",
    )

    logger.info(
        "Output file: %s",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()