"""
Source DataFrame rules and PostgreSQL target state assertions for geolocation data.
"""

from __future__ import annotations

import pandas as pd
from psycopg2 import sql

from geo_util.geo_config import (
    DB_SCHEMA,
    EXPECTED_COLUMNS,
    EXPECTED_STATES,
    TARGET_TABLE,
    logger,
)


def validate_schema(df: pd.DataFrame) -> None:
    """Validate the source schema exactly."""
    actual_columns = list(df.columns)

    missing = [c for c in EXPECTED_COLUMNS if c not in actual_columns]
    unexpected = [c for c in actual_columns if c not in EXPECTED_COLUMNS]

    if missing or unexpected:
        raise ValueError(
            "Geolocation source schema mismatch. "
            f"Missing columns: {missing}; "
            f"Unexpected columns: {unexpected}"
        )

    logger.info("Geolocation source schema validation passed.")


def validate_required_fields(df: pd.DataFrame) -> None:
    """Validate that required fields contain no null values."""
    required_columns = [
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
    ]

    null_counts = df[required_columns].isnull().sum()
    invalid = {
        column: int(count)
        for column, count in null_counts.items()
        if count > 0
    }

    if invalid:
        raise ValueError(
            f"Geolocation required-field validation failed: {invalid}"
        )

    logger.info("Geolocation required-field validation passed.")


def validate_zip_codes(df: pd.DataFrame) -> None:
    """Validate Brazilian ZIP-code prefixes."""
    series = pd.to_numeric(
        df["geolocation_zip_code_prefix"],
        errors="coerce",
    )

    if series.isnull().any():
        raise ValueError(
            "Geolocation ZIP validation failed: "
            f"{int(series.isnull().sum())} invalid ZIP prefixes."
        )

    if not series.between(0, 99999).all():
        invalid_count = int((~series.between(0, 99999)).sum())
        raise ValueError(
            "Geolocation ZIP validation failed: "
            f"{invalid_count} ZIP prefixes outside 0-99999."
        )

    if not (series % 1 == 0).all():
        raise ValueError(
            "Geolocation ZIP validation failed: "
            "ZIP prefixes must be integers."
        )

    logger.info("Geolocation ZIP validation passed.")


def validate_coordinates(df: pd.DataFrame) -> None:
    """Validate geographic coordinate ranges."""
    latitude = pd.to_numeric(df["geolocation_lat"], errors="coerce")
    longitude = pd.to_numeric(df["geolocation_lng"], errors="coerce")

    if latitude.isnull().any():
        raise ValueError(
            "Latitude validation failed: "
            f"{int(latitude.isnull().sum())} invalid values."
        )

    if longitude.isnull().any():
        raise ValueError(
            "Longitude validation failed: "
            f"{int(longitude.isnull().sum())} invalid values."
        )

    invalid_latitude = ~latitude.between(-90, 90)
    invalid_longitude = ~longitude.between(-180, 180)

    if invalid_latitude.any():
        raise ValueError(
            "Latitude validation failed: "
            f"{int(invalid_latitude.sum())} values outside [-90, 90]."
        )

    if invalid_longitude.any():
        raise ValueError(
            "Longitude validation failed: "
            f"{int(invalid_longitude.sum())} values outside [-180, 180]."
        )

    logger.info("Geolocation coordinate validation passed.")


def validate_states(df: pd.DataFrame) -> None:
    """Validate Brazilian state codes."""
    states = set(
        df["geolocation_state"]
        .astype(str)
        .str.strip()
        .str.upper()
        .unique()
    )

    invalid_states = states - EXPECTED_STATES

    if invalid_states:
        raise ValueError(
            "Geolocation state validation failed. "
            f"Unexpected state codes: {sorted(invalid_states)}"
        )

    logger.info(
        "Geolocation state validation passed: %d unique states.",
        len(states),
    )


def validate_target_is_empty(conn) -> None:
    """Ensure the target table is empty before loading."""
    query = sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
        sql.Identifier(DB_SCHEMA),
        sql.Identifier(TARGET_TABLE),
    )

    with conn.cursor() as cur:
        cur.execute(query)
        count = cur.fetchone()[0]

    if count != 0:
        raise ValueError(
            f"Target table {DB_SCHEMA}.{TARGET_TABLE} "
            f"is not empty. Existing records: {count}"
        )

    logger.info("Target table is empty and ready for loading.")


def validate_row_count(conn, expected_count: int) -> None:
    """Validate target row count."""
    query = sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
        sql.Identifier(DB_SCHEMA),
        sql.Identifier(TARGET_TABLE),
    )

    with conn.cursor() as cur:
        cur.execute(query)
        actual_count = cur.fetchone()[0]

    if actual_count != expected_count:
        raise ValueError(
            "Geolocation row-count validation failed: "
            f"expected {expected_count:,}, "
            f"found {actual_count:,}."
        )

    logger.info(
        "Geolocation row-count validation passed: %s records.",
        f"{actual_count:,}",
    )


def validate_target_duplicates(conn, expected_duplicate_count: int) -> None:
    """Validate that exact duplicates were preserved."""
    query = sql.SQL(
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                geolocation_zip_code_prefix,
                geolocation_lat,
                geolocation_lng,
                geolocation_city,
                geolocation_state,
                COUNT(*) AS record_count
            FROM {}.{}
            GROUP BY
                geolocation_zip_code_prefix,
                geolocation_lat,
                geolocation_lng,
                geolocation_city,
                geolocation_state
            HAVING COUNT(*) > 1
        ) duplicate_groups
        """
    ).format(
        sql.Identifier(DB_SCHEMA),
        sql.Identifier(TARGET_TABLE),
    )

    with conn.cursor() as cur:
        cur.execute(query)
        duplicate_groups = cur.fetchone()[0]

    if expected_duplicate_count > 0 and duplicate_groups == 0:
        raise ValueError(
            "Geolocation duplicate preservation validation failed: "
            "expected duplicate records/groups, but none were found."
        )

    logger.info("Geolocation duplicate preservation validation passed.")


def validate_target_coordinates(conn) -> None:
    """Validate coordinates after loading."""
    query = sql.SQL(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE geolocation_lat < -90
                   OR geolocation_lat > 90
            ),
            COUNT(*) FILTER (
                WHERE geolocation_lng < -180
                   OR geolocation_lng > 180
            )
        FROM {}.{}
        """
    ).format(
        sql.Identifier(DB_SCHEMA),
        sql.Identifier(TARGET_TABLE),
    )

    with conn.cursor() as cur:
        cur.execute(query)
        invalid_latitude, invalid_longitude = cur.fetchone()

    if invalid_latitude:
        raise ValueError(
            f"Target latitude validation failed: {invalid_latitude} invalid records."
        )

    if invalid_longitude:
        raise ValueError(
            f"Target longitude validation failed: {invalid_longitude} invalid records."
        )

    logger.info("Target geolocation coordinate validation passed.")