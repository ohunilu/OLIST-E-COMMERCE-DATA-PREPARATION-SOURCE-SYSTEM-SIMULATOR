#!/usr/bin/env python3
"""
Load transformed customers data into PostgreSQL.

Source:
    /app/simulated_data/customers.csv

Target:
    ecommerce.customers
"""

from __future__ import annotations

import sys

from cus_util.cus_config import SOURCE_FILE, TARGET_SCHEMA, TARGET_TABLE, logger
from cus_util.cus_db import (
    create_indexes,
    ensure_schema_and_table,
    get_connection,
    load_customers,
)
from cus_util.cus_io import (
    get_source_row_count,
    validate_source_file,
    validate_source_header,
)
from cus_util.cus_validation import (
    validate_primary_key,
    validate_required_fields,
    validate_row_count,
    validate_signup_dates,
    validate_target_is_loadable,
)


def main() -> int:
    """Execute the customers loading pipeline."""

    logger.info("=" * 60)
    logger.info("Starting Olist customers data load.")
    logger.info("=" * 60)

    connection = None

    try:
        # ---------------------------------------------------------------
        # Source validation
        # ---------------------------------------------------------------
        validate_source_file(SOURCE_FILE)
        validate_source_header(SOURCE_FILE)

        source_row_count = get_source_row_count(SOURCE_FILE)

        # ---------------------------------------------------------------
        # Database connection
        # ---------------------------------------------------------------
        connection = get_connection()
        connection.autocommit = False

        logger.info("PostgreSQL connection established successfully.")

        with connection.cursor() as cursor:
            # -----------------------------------------------------------
            # Target preparation
            # -----------------------------------------------------------
            ensure_schema_and_table(cursor)
            validate_target_is_loadable(cursor)

            # -----------------------------------------------------------
            # Data loading
            # -----------------------------------------------------------
            load_customers(cursor, SOURCE_FILE)

            # -----------------------------------------------------------
            # Post-load validation
            # -----------------------------------------------------------
            validate_row_count(cursor, source_row_count)
            validate_primary_key(cursor)
            validate_required_fields(cursor)
            validate_signup_dates(cursor)

            # -----------------------------------------------------------
            # Index creation
            # -----------------------------------------------------------
            create_indexes(cursor)

        # ---------------------------------------------------------------
        # Commit transaction
        # ---------------------------------------------------------------
        connection.commit()

        logger.info("Customers transaction committed successfully.")
        logger.info("=" * 60)
        logger.info("Customers load completed successfully.")
        logger.info("Source records: %s", f"{source_row_count:,}")
        logger.info("Target table: %s.%s", TARGET_SCHEMA, TARGET_TABLE)
        logger.info("Target records: %s", f"{source_row_count:,}")
        logger.info("=" * 60)

        return 0

    except Exception as exc:
        logger.error("Customers load FAILED: %s", exc)

        if connection is not None:
            try:
                connection.rollback()
                logger.error("Transaction rolled back successfully.")
            except Exception as rollback_error:
                logger.error(
                    "Transaction rollback failed: %s",
                    rollback_error,
                )

        return 1

    finally:
        if connection is not None:
            connection.close()
            logger.info("PostgreSQL connection closed.")


if __name__ == "__main__":
    sys.exit(main())