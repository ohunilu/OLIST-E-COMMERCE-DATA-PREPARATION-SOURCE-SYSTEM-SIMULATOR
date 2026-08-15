from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from geolocation_util.geolocation_config import (
    OUTPUT_FILE,
    SOURCE_FILE,
)

logger = logging.getLogger(__name__)


def load_source_data() -> pd.DataFrame:
    """Load the Olist geolocation source dataset."""
    logger.info("Reading source file: %s", SOURCE_FILE)

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