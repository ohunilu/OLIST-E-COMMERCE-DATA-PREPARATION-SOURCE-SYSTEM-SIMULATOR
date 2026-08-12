"""
Transform Olist seller data into a clean simulated source-system dataset.

Input:
    /app/source_data/olist_sellers_dataset.csv

Output:
    /app/simulated_data/sellers.csv

Purpose:
    Prepare the Olist seller dataset for loading into the simulated
    PostgreSQL operational source system used by the CustomerPulse project.

Design principles:
    - Preserve all source seller records.
    - Preserve seller identifiers.
    - Do not introduce synthetic seller attributes.
    - Do not apply temporal transformations because the dataset contains
      no timestamp fields.
    - Standardize textual fields conservatively.
    - Fail fast on structural or data-quality violations.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_FILE = Path(
    "/app/source_data/olist_sellers_dataset.csv"
)

OUTPUT_FILE = Path(
    "/app/simulated_data/sellers.csv"
)


EXPECTED_COLUMNS = [
    "seller_id",
    "seller_zip_code_prefix",
    "seller_city",
    "seller_state",
]


VALID_STATE_LENGTH = 2


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------

def validate_file_exists(
    path: Path,
    description: str,
) -> None:
    """Validate that an input file exists."""

    if not path.exists():
        raise FileNotFoundError(
            f"{description} not found: {path}"
        )


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def validate_source_schema(
    df: pd.DataFrame,
) -> None:
    """Validate the seller source schema."""

    actual_columns = list(df.columns)

    if actual_columns != EXPECTED_COLUMNS:
        raise ValueError(
            "Unexpected seller source schema.\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Actual:   {actual_columns}"
        )

    logger.info(
        "Source schema validation passed."
    )


# ---------------------------------------------------------------------------
# Seller key validation
# ---------------------------------------------------------------------------

def validate_seller_keys(
    df: pd.DataFrame,
) -> None:
    """Validate seller_id as the primary key."""

    if df["seller_id"].isna().any():
        raise ValueError(
            "seller_id contains NULL values."
        )

    duplicate_count = (
        df["seller_id"]
        .duplicated()
        .sum()
    )

    if duplicate_count > 0:
        raise ValueError(
            "Duplicate seller_id values detected: "
            f"{duplicate_count}"
        )

    logger.info(
        "Seller key validation passed."
    )


# ---------------------------------------------------------------------------
# Required field validation
# ---------------------------------------------------------------------------

def validate_required_fields(
    df: pd.DataFrame,
) -> None:
    """Validate required seller attributes."""

    required_columns = EXPECTED_COLUMNS

    null_counts = (
        df[required_columns]
        .isna()
        .sum()
    )

    invalid = null_counts[
        null_counts > 0
    ]

    if not invalid.empty:
        raise ValueError(
            "Required seller fields contain NULL values:\n"
            f"{invalid.to_string()}"
        )

    logger.info(
        "Required field validation passed."
    )


# ---------------------------------------------------------------------------
# Text standardization
# ---------------------------------------------------------------------------

def standardize_text_fields(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Standardize textual seller attributes.

    This deliberately performs only conservative formatting:
        - trim leading/trailing whitespace
        - convert state to uppercase

    City names are retained in the source's lowercase representation.
    """

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

    logger.info(
        "Seller text standardization completed."
    )

    return df


# ---------------------------------------------------------------------------
# Numeric validation
# ---------------------------------------------------------------------------

def validate_numeric_values(
    df: pd.DataFrame,
) -> None:
    """Validate seller numeric attributes."""

    if (
        df["seller_zip_code_prefix"] < 0
    ).any():
        invalid_count = (
            df["seller_zip_code_prefix"] < 0
        ).sum()

        raise ValueError(
            "Negative seller ZIP code prefixes detected: "
            f"{invalid_count}"
        )

    logger.info(
        "Numeric value validation passed."
    )


# ---------------------------------------------------------------------------
# State validation
# ---------------------------------------------------------------------------

def validate_state_values(
    df: pd.DataFrame,
) -> None:
    """Validate Brazilian state/UF codes."""

    invalid_length = (
        df["seller_state"]
        .str.len()
        .ne(VALID_STATE_LENGTH)
    )

    if invalid_length.any():
        invalid_count = invalid_length.sum()

        raise ValueError(
            "Invalid seller_state length detected: "
            f"{invalid_count}"
        )

    invalid_values = sorted(
        df.loc[
            ~df["seller_state"].str.match(
                r"^[A-Z]{2}$"
            ),
            "seller_state",
        ].unique()
    )

    if invalid_values:
        raise ValueError(
            "Invalid seller_state values detected: "
            f"{invalid_values}"
        )

    logger.info(
        "Seller state validation passed."
    )


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------

def validate_output(
    df: pd.DataFrame,
    source_record_count: int,
) -> None:
    """Validate the final transformed seller dataset."""

    if len(df) != source_record_count:
        raise ValueError(
            "Output row count changed.\n"
            f"Source: {source_record_count}\n"
            f"Output: {len(df)}"
        )

    logger.info(
        "Output row-count validation passed: %s records.",
        f"{len(df):,}",
    )

    if list(df.columns) != EXPECTED_COLUMNS:
        raise ValueError(
            "Output schema does not match expected schema.\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Actual:   {list(df.columns)}"
        )

    duplicate_count = (
        df["seller_id"]
        .duplicated()
        .sum()
    )

    if duplicate_count > 0:
        raise ValueError(
            "Output contains duplicate seller_id values: "
            f"{duplicate_count}"
        )

    if df[EXPECTED_COLUMNS].isna().any().any():
        raise ValueError(
            "Output contains unexpected NULL values."
        )

    logger.info(
        "Output seller key validation passed."
    )

    logger.info(
        "Output schema validation passed."
    )


# ---------------------------------------------------------------------------
# Main transformation
# ---------------------------------------------------------------------------

def main() -> None:
    """Execute the complete seller transformation."""

    logger.info(
        "Starting Olist sellers dataset transformation."
    )

    # -----------------------------------------------------------------------
    # Validate input
    # -----------------------------------------------------------------------

    validate_file_exists(
        SOURCE_FILE,
        "Seller source file",
    )

    # -----------------------------------------------------------------------
    # Read source
    # -----------------------------------------------------------------------

    logger.info(
        "Reading source file: %s",
        SOURCE_FILE,
    )

    sellers_df = pd.read_csv(
        SOURCE_FILE
    )

    source_record_count = len(
        sellers_df
    )

    logger.info(
        "Source records loaded: %s",
        f"{source_record_count:,}",
    )

    # -----------------------------------------------------------------------
    # Source validation
    # -----------------------------------------------------------------------

    validate_source_schema(
        sellers_df
    )

    validate_seller_keys(
        sellers_df
    )

    validate_required_fields(
        sellers_df
    )

    validate_numeric_values(
        sellers_df
    )

    # -----------------------------------------------------------------------
    # Standardization
    # -----------------------------------------------------------------------

    sellers_df = standardize_text_fields(
        sellers_df
    )

    validate_state_values(
        sellers_df
    )

    # -----------------------------------------------------------------------
    # Output validation
    # -----------------------------------------------------------------------

    validate_output(
        sellers_df,
        source_record_count,
    )

    # -----------------------------------------------------------------------
    # Write output
    # -----------------------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    sellers_df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    logger.info(
        "Output file written: %s",
        OUTPUT_FILE,
    )

    logger.info(
        "Seller transformation completed successfully."
    )

    logger.info(
        "Source records: %s",
        f"{source_record_count:,}",
    )

    logger.info(
        "Output records: %s",
        f"{len(sellers_df):,}",
    )

    logger.info(
        "Output file: %s",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()