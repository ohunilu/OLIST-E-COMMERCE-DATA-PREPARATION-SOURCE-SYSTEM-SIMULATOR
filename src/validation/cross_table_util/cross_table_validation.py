from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def validate_required_columns(
    dataframe: pd.DataFrame,
    required_columns: list[str],
    table_name: str,
) -> None:
    """Validate required columns."""
    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"{table_name} is missing required columns: "
            f"{missing_columns}"
        )


def validate_unique_key(
    dataframe: pd.DataFrame,
    columns: list[str],
    table_name: str,
) -> None:
    """Validate uniqueness of a single or composite key."""
    duplicate_count = dataframe.duplicated(subset=columns).sum()

    if duplicate_count > 0:
        raise ValueError(
            f"{table_name} contains {duplicate_count:,} "
            f"duplicate records for key {columns}."
        )


def validate_foreign_key(
    child: pd.DataFrame,
    child_column: str,
    parent: pd.DataFrame,
    parent_column: str,
    relationship_name: str,
) -> None:
    """
    Validate that every non-null child foreign key exists in the parent.
    """
    child_values = set(child[child_column].dropna())
    parent_values = set(parent[parent_column].dropna())
    missing_values = child_values - parent_values

    if missing_values:
        sample = list(missing_values)[:10]
        raise ValueError(
            f"{relationship_name} validation failed: "
            f"{len(missing_values):,} child values do not exist "
            f"in the parent table. Sample: {sample}"
        )

    logger.info(
        "%s validation passed.",
        relationship_name,
    )


def normalize_zip_codes(series: pd.Series) -> pd.Series:
    """
    Normalize ZIP-code prefixes to five-character strings.

    The Olist data represents Brazilian ZIP prefixes as integers, which can
    remove leading zeroes. Normalization ensures reliable comparison.
    """
    return (
        series
        .dropna()
        .astype(int)
        .astype(str)
        .str.zfill(5)
    )


def validate_customer_zip_coverage(
    customers: pd.DataFrame,
    geolocation: pd.DataFrame,
) -> float:
    customer_zips = set(
        normalize_zip_codes(
            customers["zip_code_prefix"]
        )
    )

    geolocation_zips = set(
        normalize_zip_codes(
            geolocation["geolocation_zip_code_prefix"]
        )
    )

    missing_customer_zips = customer_zips - geolocation_zips
    matched_customer_zips = customer_zips & geolocation_zips

    if missing_customer_zips:
        logger.warning(
            "Customer ZIP coverage is incomplete."
        )
        logger.warning(
            "Customer ZIP prefixes: %s",
            f"{len(customer_zips):,}",
        )
        logger.warning(
            "ZIP prefixes found in geolocation: %s",
            f"{len(matched_customer_zips):,}",
        )
        logger.warning(
            "ZIP prefixes without geolocation mapping: %s",
            f"{len(missing_customer_zips):,}",
        )
        logger.warning(
            "Sample missing ZIP prefixes: %s",
            sorted(missing_customer_zips)[:20],
        )
    else:
        logger.info(
            "Customer → geolocation ZIP coverage validation passed."
        )

    coverage_percent = (
        len(matched_customer_zips) / len(customer_zips) * 100
        if customer_zips
        else 100.0
    )

    logger.info(
        "Customer ZIP coverage: %.2f%%",
        coverage_percent,
    )

    return coverage_percent