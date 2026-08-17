from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from product_util.product_config import (
    OUTPUT_FILE,
    SOURCE_FILE,
    TRANSLATION_FILE,
)

logger = logging.getLogger(__name__)


def load_source_data() -> pd.DataFrame:
    logger.info("Reading source file: %s", SOURCE_FILE)

    if not SOURCE_FILE.exists():
        raise FileNotFoundError(f"Source file not found: {SOURCE_FILE}")

    df = pd.read_csv(SOURCE_FILE)

    logger.info("Source records loaded: %s", f"{len(df):,}")

    return df


def load_translation_data() -> pd.DataFrame:
    logger.info("Reading translation reference: %s", TRANSLATION_FILE)

    if not TRANSLATION_FILE.exists():
        raise FileNotFoundError(
            f"Translation file not found: {TRANSLATION_FILE}"
        )

    translation_df = pd.read_csv(TRANSLATION_FILE)

    logger.info(
        "Translation records loaded: %s",
        f"{len(translation_df):,}",
    )

    return translation_df


def write_output(df: pd.DataFrame) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    logger.info(
        "Output file written: %s",
        OUTPUT_FILE,
    )