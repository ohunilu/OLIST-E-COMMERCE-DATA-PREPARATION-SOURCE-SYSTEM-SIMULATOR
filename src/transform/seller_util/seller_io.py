from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from seller_util.seller_config import OUTPUT_FILE, SOURCE_FILE

logger = logging.getLogger(__name__)


def validate_file_exists(path: Path, description: str) -> None:
    """Validate that an input file exists."""
    if not path.exists():
        raise FileNotFoundError(
            f"{description} not found: {path}"
        )


def read_source_data() -> pd.DataFrame:
    logger.info("Reading source file: %s", SOURCE_FILE)

    df = pd.read_csv(SOURCE_FILE)

    logger.info(
        "Source records loaded: %s",
        f"{len(df):,}",
    )

    return df


def write_output(df: pd.DataFrame) -> None:
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