"""
Source file verification and reading routines for payments data.
"""

from __future__ import annotations

import os
from pathlib import Path
import pandas as pd

from pay_util.pay_config import SOURCE_FILE, logger


def validate_source_file_existence() -> None:
    """Validate that the source CSV exists and is readable."""
    logger.info("Reading payments source file: %s", SOURCE_FILE)

    source_path = Path(SOURCE_FILE)

    if not source_path.exists():
        raise FileNotFoundError(
            f"Payments source file not found: {SOURCE_FILE}"
        )

    logger.info("Payments source file validation passed.")


def read_source_file() -> pd.DataFrame:
    """Read the source payments CSV file into a Pandas DataFrame."""
    validate_source_file_existence()
    return pd.read_csv(SOURCE_FILE)