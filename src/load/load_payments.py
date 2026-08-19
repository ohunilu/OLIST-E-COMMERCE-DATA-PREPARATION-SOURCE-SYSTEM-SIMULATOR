#!/usr/bin/env python3
"""
Load transformed Olist payment data into PostgreSQL.

Source:
    /app/simulated_data/payments.csv

Target:
    public.payments

Known source-data anomaly:
    Two credit-card payment records contain payment_installments = 0.
    These records are preserved intentionally and validated after loading.
"""

from __future__ import annotations

import sys

from pay_util.pay_config import (
    KNOWN_ZERO_INSTALLMENT_COUNT,
    SCHEMA_NAME,
    TABLE_NAME,
    logger,
)
from pay_util.pay_db import (
    bulk_load,
    create_indexes,
    ensure_schema,
    ensure_target_table,
    get_connection,
)
from pay_util.pay_io import read_source_file
from pay_util.pay_validation import (
    validate_foreign_key_after_load,
    validate_installment_anomalies_after_load,
    validate_orders_foreign_key,
    validate_primary_key,
    validate_row_count,
    validate_source_dataframe,
    validate_target_is_empty,
    validate_target_required_fields,
)


def main() -> int:
    """Execute the payments loading pipeline."""
    conn = None

    try:
        logger.info("=" * 60)
        logger.info("Starting Olist payments data load.")
        logger.info("=" * 60)

        # --------------------------------------------------------------
        # Source read and validation
        # --------------------------------------------------------------
        df = read_source_file()
        df = validate_source_dataframe(df)

        source_count = len(df)

        # --------------------------------------------------------------
        # Database connection & setup
        # --------------------------------------------------------------
        conn = get_connection()

        ensure_schema(conn)
        ensure_target_table(conn)
        validate_target_is_empty(conn)

        # --------------------------------------------------------------
        # Cross-table validation
        # --------------------------------------------------------------
        validate_orders_foreign_key(conn, df)

        # --------------------------------------------------------------
        # Bulk load
        # --------------------------------------------------------------
        bulk_load(conn, df)

        # --------------------------------------------------------------
        # Post-load validation
        # --------------------------------------------------------------
        validate_row_count(conn, source_count)
        validate_primary_key(conn)
        validate_target_required_fields(conn)
        validate_foreign_key_after_load(conn)
        validate_installment_anomalies_after_load(conn)

        # --------------------------------------------------------------
        # Indexes
        # --------------------------------------------------------------
        create_indexes(conn)

        # --------------------------------------------------------------
        # Commit
        # --------------------------------------------------------------
        conn.commit()

        logger.info("Payments transaction committed successfully.")
        logger.info("=" * 60)
        logger.info("Payments load completed successfully.")
        logger.info("Source records: %s", source_count)
        logger.info("Target table: %s.%s", SCHEMA_NAME, TABLE_NAME)
        logger.info("Target records: %s", source_count)
        logger.info(
            "Known zero-installment anomalies preserved: %s",
            KNOWN_ZERO_INSTALLMENT_COUNT,
        )
        logger.info("=" * 60)

        return 0

    except Exception as exc:
        if conn is not None:
            conn.rollback()

        logger.error("Payments load FAILED: %s", exc)
        return 1

    finally:
        if conn is not None:
            conn.close()
            logger.info("PostgreSQL connection closed.")


if __name__ == "__main__":
    sys.exit(main())