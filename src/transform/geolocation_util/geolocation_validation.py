from __future__ import annotations

import logging

import pandas as pd

from geolocation_util.geolocation_config import (
    EXPECTED_COLUMNS,
    LATITUDE_MAX,
    LATITUDE_MIN,
    LONGITUDE_MAX,
    LONGITUDE_MIN,
    REQUIRED_COLUMNS,
)

logger = logging.getLogger(__name__)


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


def validate_geographic_values(df: pd.DataFrame) -> None:
    """
    Detect geographic coordinate anomalies.

    Out-of-range values are logged as source anomalies and preserved.
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


def analyze_duplicates(df: pd.DataFrame) -> None:
    """
    Analyze duplicate records without removing them.
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

    logger.info("Duplicate analysis completed.")
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
    logger.info("No duplicate records were removed.")


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