"""
Source file parsing and duplicate structure analysis for geolocation data.
"""

from __future__ import annotations

import os
from pathlib import Path
import pandas as pd

from geo_util.geo_config import SOURCE_FILE, logger


def validate_source_file() -> None:
    """Validate that the source file exists and is readable."""
    source_path = Path(SOURCE_FILE)

    if not source_path.exists():
        raise FileNotFoundError(
            f"Geolocation source file not found: {SOURCE_FILE}"
        )

    if source_path.stat().st_size == 0:
        raise ValueError(
            f"Geolocation source file is empty: {SOURCE_FILE}"
        )

    logger.info("Geolocation source file validation passed.")


def analyze_duplicates(df: pd.DataFrame) -> int:
    """Analyze exact duplicate records in the geolocation dataset."""
    duplicate_count = int(df.duplicated().sum())
    unique_zip_count = int(df["geolocation_zip_code_prefix"].nunique())

    multiple_zip_count = int(
        (df.groupby("geolocation_zip_code_prefix").size().gt(1)).sum()
    )

    max_records_per_zip = int(
        df.groupby("geolocation_zip_code_prefix").size().max()
    )

    logger.info("Duplicate analysis completed.")
    logger.info(
        "Exact duplicate source records preserved: %d", duplicate_count
    )
    logger.info("Unique ZIP prefixes: %d", unique_zip_count)
    logger.info(
        "ZIP prefixes with multiple observations: %d", multiple_zip_count
    )
    logger.info("Maximum observations for one ZIP prefix: %d", max_records_per_zip)
    logger.info("No duplicate records will be removed.")

    return duplicate_count