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


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_FILE = Path(
    "/app/source_data/olist_geolocation_dataset.csv"
)

OUTPUT_FILE = Path(
    "/app/simulated_data/geolocation.csv"
)

EXPECTED_COLUMNS = [
    "geolocation_zip_code_prefix",
    "geolocation_lat",
    "geolocation_lng",
    "geolocation_city",
    "geolocation_state",
]

REQUIRED_COLUMNS = EXPECTED_COLUMNS

LATITUDE_MIN = -90.0
LATITUDE_MAX = 90.0

LONGITUDE_MIN = -180.0
LONGITUDE_MAX = 180.0


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
    """Load the Olist geolocation source dataset."""

    logger.info(
        "Reading source file: %s",
        SOURCE_FILE,
    )

    if not SOURCE_FILE.exists():
        raise FileNotFoundError(
            f"Source file not found: {SOURCE_FILE}"
        )

    df = pd.read_csv(SOURCE_FILE)

    logger.info(
        "Source records loaded: %s",
        f"{len(df):,}",
    )

    return df


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def validate_source_schema(df: pd.DataFrame) -> None:
    """Validate the source dataset schema."""

    actual_columns = df.columns.tolist()

    missing_columns = [
        column
        for column in EXPECTED_COLUMNS
        if column not in actual_columns
    ]

    unexpected_columns = [
        column
        for column in actual_columns
        if column not in EXPECTED_COLUMNS
    ]

    if missing_columns:
        raise ValueError(
            "Source schema validation failed. "
            f"Missing columns: {missing_columns}"
        )

    if unexpected_columns:
        logger.warning(
            "Source contains unexpected columns: %s",
            unexpected_columns,
        )

    logger.info("Source schema validation passed.")


# ---------------------------------------------------------------------------
# Required-field validation
# ---------------------------------------------------------------------------

def validate_required_fields(df: pd.DataFrame) -> None:
    """Validate that required fields do not contain NULL values."""

    null_counts = df[REQUIRED_COLUMNS].isna().sum()

    invalid_nulls = null_counts[null_counts > 0]

    if not invalid_nulls.empty:
        raise ValueError(
            "Required field validation failed. "
            f"NULL counts: {invalid_nulls.to_dict()}"
        )

    logger.info("Required field validation passed.")


# ---------------------------------------------------------------------------
# ZIP code validation
# ---------------------------------------------------------------------------

def validate_zip_codes(df: pd.DataFrame) -> None:
    """Validate geolocation ZIP code prefixes."""

    zip_values = df["geolocation_zip_code_prefix"]

    if not pd.api.types.is_numeric_dtype(zip_values):
        raise ValueError(
            "ZIP code prefix validation failed: "
            "geolocation_zip_code_prefix must be numeric."
        )

    negative_count = (zip_values < 0).sum()

    if negative_count > 0:
        raise ValueError(
            "ZIP code prefix validation failed: "
            f"{negative_count:,} negative ZIP prefixes found."
        )

    if zip_values.isna().any():
        raise ValueError(
            "ZIP code prefix validation failed: NULL values found."
        )

    logger.info("ZIP code prefix validation passed.")


# ---------------------------------------------------------------------------
# Geographic validation
# ---------------------------------------------------------------------------

def validate_geographic_values(df: pd.DataFrame) -> None:
    """
    Detect geographic coordinate anomalies.

    Out-of-range values are logged as source anomalies and preserved.
    They are not silently corrected or removed.
    """

    latitude_outliers = (
        (df["geolocation_lat"] < LATITUDE_MIN)
        | (df["geolocation_lat"] > LATITUDE_MAX)
    )

    longitude_outliers = (
        (df["geolocation_lng"] < LONGITUDE_MIN)
        | (df["geolocation_lng"] > LONGITUDE_MAX)
    )

    latitude_count = int(latitude_outliers.sum())
    longitude_count = int(longitude_outliers.sum())

    if latitude_count > 0:
        logger.warning(
            "Source geographic anomaly: latitude outside "
            "[-90, 90] | rows=%s",
            f"{latitude_count:,}",
        )
    else:
        logger.info(
            "Latitude validation passed: all values within [-90, 90]."
        )

    if longitude_count > 0:
        logger.warning(
            "Source geographic anomaly: longitude outside "
            "[-180, 180] | rows=%s",
            f"{longitude_count:,}",
        )
    else:
        logger.info(
            "Longitude validation passed: all values within [-180, 180]."
        )

    if latitude_count == 0 and longitude_count == 0:
        logger.info("Geographic coordinate validation passed.")
    else:
        logger.warning(
            "Source geographic anomalies preserved: %s rows.",
            f"{latitude_count + longitude_count:,}",
        )


# ---------------------------------------------------------------------------
# Duplicate analysis
# ---------------------------------------------------------------------------

def analyze_duplicates(df: pd.DataFrame) -> None:
    """
    Analyze duplicate records without removing them.

    The Olist geolocation dataset contains multiple observations per ZIP
    prefix and may also contain exact duplicate observations. Both are
    preserved intentionally.
    """

    duplicate_rows = int(df.duplicated().sum())

    unique_zip_prefixes = int(
        df["geolocation_zip_code_prefix"].nunique()
    )

    zip_counts = df.groupby(
        "geolocation_zip_code_prefix"
    ).size()

    repeated_zip_prefixes = int(
        (zip_counts > 1).sum()
    )

    maximum_records_per_zip = int(
        zip_counts.max()
    )

    logger.info(
        "Duplicate analysis completed."
    )

    logger.info(
        "Exact duplicate source records preserved: %s",
        f"{duplicate_rows:,}",
    )

    logger.info(
        "Unique ZIP prefixes: %s",
        f"{unique_zip_prefixes:,}",
    )

    logger.info(
        "ZIP prefixes with multiple observations: %s",
        f"{repeated_zip_prefixes:,}",
    )

    logger.info(
        "Maximum observations for one ZIP prefix: %s",
        f"{maximum_records_per_zip:,}",
    )

    logger.info(
        "No duplicate records were removed."
    )


# ---------------------------------------------------------------------------
# Text standardization
# ---------------------------------------------------------------------------

def standardize_text_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize geolocation city and state fields.

    City values are:
        - converted to string
        - trimmed
        - normalized to lowercase

    State values are:
        - converted to string
        - trimmed
        - normalized to uppercase
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

    logger.info(
        "Geolocation text standardization completed."
    )

    return df


# ---------------------------------------------------------------------------
# State validation
# ---------------------------------------------------------------------------

def validate_states(df: pd.DataFrame) -> None:
    """Validate standardized state values."""

    null_states = df["geolocation_state"].isna().sum()

    if null_states > 0:
        raise ValueError(
            "State validation failed: "
            f"{null_states:,} NULL state values found."
        )

    empty_states = (
        df["geolocation_state"].astype("string").str.strip().eq("")
    ).sum()

    if empty_states > 0:
        raise ValueError(
            "State validation failed: "
            f"{empty_states:,} empty state values found."
        )

    state_count = df["geolocation_state"].nunique()

    logger.info(
        "Geolocation state validation passed: %s unique states.",
        state_count,
    )


# ---------------------------------------------------------------------------
# Output schema validation
# ---------------------------------------------------------------------------

def validate_output_schema(df: pd.DataFrame) -> None:
    """Validate the final output schema."""

    actual_columns = df.columns.tolist()

    if actual_columns != EXPECTED_COLUMNS:
        raise ValueError(
            "Output schema validation failed.\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Actual:   {actual_columns}"
        )

    logger.info("Output schema validation passed.")


# ---------------------------------------------------------------------------
# Output row-count validation
# ---------------------------------------------------------------------------

def validate_output_row_count(
    source_df: pd.DataFrame,
    output_df: pd.DataFrame,
) -> None:
    """Ensure no source records were lost or added."""

    source_count = len(source_df)
    output_count = len(output_df)

    if source_count != output_count:
        raise ValueError(
            "Output row-count validation failed. "
            f"Source={source_count:,}, "
            f"Output={output_count:,}"
        )

    logger.info(
        "Output row-count validation passed: %s records.",
        f"{output_count:,}",
    )


# ---------------------------------------------------------------------------
# Output duplicate validation
# ---------------------------------------------------------------------------

def validate_output_duplicates(
    source_df: pd.DataFrame,
    output_df: pd.DataFrame,
) -> None:
    """Ensure duplicate preservation is consistent with the source."""

    source_duplicates = int(
        source_df.duplicated().sum()
    )

    output_duplicates = int(
        output_df.duplicated().sum()
    )

    if source_duplicates != output_duplicates:
        raise ValueError(
            "Duplicate preservation validation failed. "
            f"Source duplicates={source_duplicates:,}, "
            f"Output duplicates={output_duplicates:,}"
        )

    logger.info(
        "Duplicate preservation validation passed: %s exact duplicates.",
        f"{output_duplicates:,}",
    )


# ---------------------------------------------------------------------------
# Data type validation
# ---------------------------------------------------------------------------

def validate_output_data_types(df: pd.DataFrame) -> None:
    """Validate important output data types."""

    if not pd.api.types.is_numeric_dtype(
        df["geolocation_zip_code_prefix"]
    ):
        raise ValueError(
            "Output ZIP prefix must be numeric."
        )

    if not pd.api.types.is_numeric_dtype(
        df["geolocation_lat"]
    ):
        raise ValueError(
            "Output latitude must be numeric."
        )

    if not pd.api.types.is_numeric_dtype(
        df["geolocation_lng"]
    ):
        raise ValueError(
            "Output longitude must be numeric."
        )

    logger.info("Output data type validation passed.")


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------

def write_output(df: pd.DataFrame) -> None:
    """Write transformed data to the simulated source layer."""

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
    """Execute the complete geolocation transformation pipeline."""

    logger.info(
        "Starting Olist geolocation dataset transformation."
    )

    # ------------------------------------------------------------------
    # 1. Load
    # ------------------------------------------------------------------

    source_df = load_source_data()

    # ------------------------------------------------------------------
    # 2. Validate source
    # ------------------------------------------------------------------

    validate_source_schema(source_df)
    validate_required_fields(source_df)
    validate_zip_codes(source_df)

    # ------------------------------------------------------------------
    # 3. Analyze source characteristics
    # ------------------------------------------------------------------

    analyze_duplicates(source_df)
    validate_geographic_values(source_df)

    # ------------------------------------------------------------------
    # 4. Transform
    # ------------------------------------------------------------------

    transformed_df = standardize_text_fields(source_df)

    # ------------------------------------------------------------------
    # 5. Validate transformed data
    # ------------------------------------------------------------------

    validate_states(transformed_df)
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

    # ------------------------------------------------------------------
    # 6. Write
    # ------------------------------------------------------------------

    write_output(transformed_df)

    # ------------------------------------------------------------------
    # 7. Summary
    # ------------------------------------------------------------------

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