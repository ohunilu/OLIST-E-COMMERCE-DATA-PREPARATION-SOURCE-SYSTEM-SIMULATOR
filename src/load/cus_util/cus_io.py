"""
Input/Output utility functions for handling source files.
"""

from __future__ import annotations

from pathlib import Path

from cus_util.cus_config import EXPECTED_COLUMNS, logger


def validate_source_file(source_file: Path) -> None:
    """Validate that the transformed customers file exists."""
    logger.info("Reading customers source file: %s", source_file)

    if not source_file.exists():
        raise FileNotFoundError(
            f"Customers source file does not exist: {source_file}"
        )

    if not source_file.is_file():
        raise ValueError(
            f"Customers source path is not a regular file: {source_file}"
        )

    if source_file.stat().st_size == 0:
        raise ValueError(
            f"Customers source file is empty: {source_file}"
        )

    logger.info("Customers source file validation passed.")


def get_source_row_count(source_file: Path) -> int:
    """
    Count source records without loading the entire CSV into memory.

    Assumes the first line is the CSV header.
    """
    with source_file.open("r", encoding="utf-8", newline="") as file:
        row_count = sum(1 for _ in file) - 1

    if row_count < 0:
        raise ValueError(
            "Customers source file does not contain a valid CSV header."
        )

    logger.info(
        "Source records available for loading: %s",
        f"{row_count:,}",
    )

    return row_count


def validate_source_header(source_file: Path) -> None:
    """Validate the CSV header against the expected customers schema."""
    with source_file.open("r", encoding="utf-8", newline="") as file:
        header_line = file.readline().strip()

    if not header_line:
        raise ValueError("Customers CSV does not contain a header.")

    actual_columns = [
        column.strip().strip('"')
        for column in header_line.split(",")
    ]

    if actual_columns != EXPECTED_COLUMNS:
        raise ValueError(
            "Customers source schema mismatch.\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Found:    {actual_columns}"
        )

    logger.info("Customers source schema validation passed.")