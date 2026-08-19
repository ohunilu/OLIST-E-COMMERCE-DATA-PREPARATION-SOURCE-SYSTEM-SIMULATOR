#!/usr/bin/env python3
"""
Load transformed Olist geolocation data into PostgreSQL.

Source:
    /app/simulated_data/geolocation.csv

Target:
    public.geolocation
"""

from __future__ import annotations

import sys
import pandas as pd

from geo_util.geo_config import DB_SCHEMA, SOURCE_FILE, TARGET_TABLE, logger
from geo_util.geo_db import (
    bulk_load,
    create_indexes,
    ensure_schema,
    ensure_table,
    get_connection,
)
from geo_util.geo_io import analyze_duplicates, validate_source_file
from geo_util.geo_validation import (
    validate_coordinates,
    validate_required_fields,
    validate_row_count,
    validate_schema,
    validate_states,
    validate_target_coordinates,
    validate_target_duplicates,
    validate_target_is_empty,
    validate_zip_codes,
)


def main() -> int:
    """Execute the geolocation loading pipeline."""

    logger.info("=" * 60)
    logger.info("Starting Olist geolocation data load.")
    logger.info("=" * 60)

    conn = None

    try:
        # -------------------------------------------------------------
        # Source validation
        # -------------------------------------------------------------
        validate_source_file()

        logger.info(
            "Reading geolocation source file: %s",
            SOURCE_FILE,
        )

        df = pd.read_csv(SOURCE_FILE)

        validate_schema(df)

        source_count = len(df)

        logger.info(
            "Source records available for loading: %s",
            f"{source_count:,}",
        )

        validate_required_fields(df)
        validate_zip_codes(df)
        validate_coordinates(df)
        validate_states(df)

        expected_duplicate_count = analyze_duplicates(df)

        # -------------------------------------------------------------
        # PostgreSQL Setup
        # -------------------------------------------------------------
        conn = get_connection()

        ensure_schema(conn)
        ensure_table(conn)
        validate_target_is_empty(conn)

        # -------------------------------------------------------------
        # Load
        # -------------------------------------------------------------
        bulk_load(conn, df)

        # -------------------------------------------------------------
        # Post-load validation
        # -------------------------------------------------------------
        validate_row_count(conn, source_count)
        validate_target_duplicates(conn, expected_duplicate_count)
        validate_target_coordinates(conn)

        # -------------------------------------------------------------
        # Indexes
        # -------------------------------------------------------------
        create_indexes(conn)

        # -------------------------------------------------------------
        # Commit
        # -------------------------------------------------------------
        conn.commit()

        logger.info("Geolocation transaction committed successfully.")
        logger.info("=" * 60)
        logger.info("Geolocation load completed successfully.")
        logger.info("Source records: %s", f"{source_count:,}")
        logger.info("Target table: %s.%s", DB_SCHEMA, TARGET_TABLE)
        logger.info("Target records: %s", f"{source_count:,}")
        logger.info(
            "Unique ZIP prefixes: %s",
            f"{df['geolocation_zip_code_prefix'].nunique():,}",
        )
        logger.info(
            "Exact duplicate source records preserved: %s",
            f"{expected_duplicate_count:,}",
        )
        logger.info("=" * 60)

        return 0

    except Exception as exc:
        logger.error("Geolocation load FAILED: %s", exc)

        if conn is not None:
            conn.rollback()
            logger.error("Geolocation transaction rolled back.")

        return 1

    finally:
        if conn is not None:
            conn.close()
            logger.info("PostgreSQL connection closed.")


if __name__ == "__main__":
    sys.exit(main())