"""
Main execution module for loading Olist order_items into PostgreSQL.
"""

import sys
from ori_util.ori_db import bulk_load, connect_database, create_indexes, ensure_schema_and_table
from ori_util.ori_config import SCHEMA_NAME, TABLE_NAME, logger
from ori_util.ori_validation import (
    validate_foreign_keys,
    validate_loaded_data,
    validate_source_data,
    validate_source_file,
    validate_target_is_empty,
)


def main() -> None:
    logger.info("=" * 60)
    logger.info("Starting Olist order_items data load.")
    logger.info("=" * 60)

    conn = None

    try:
        # Step 1: Ingest and Validate Source Data
        df = validate_source_file()
        validate_source_data(df)
        record_count = len(df)

        # Step 2: Establish DB Session & Validate Target Table State
        conn = connect_database()
        ensure_schema_and_table(conn)
        validate_target_is_empty(conn)

        # Step 3: Verify Foreign Key Dependencies Before Bulk Load
        validate_foreign_keys(conn, df)

        # Step 4: Stream Data to PostgreSQL via COPY
        bulk_load(conn, df)

        # Step 5: Post-Load Assertions & Index Creation
        validate_loaded_data(conn, expected_count=record_count)
        create_indexes(conn)

        # Step 6: Commit Transaction
        conn.commit()
        logger.info("Order_items transaction committed successfully.")

        logger.info("=" * 60)
        logger.info("Order_items load completed successfully.")
        logger.info("Source records: %s", f"{record_count:,}")
        logger.info("Target table: %s.%s", SCHEMA_NAME, TABLE_NAME)
        logger.info("Target records: %s", f"{record_count:,}")
        logger.info("=" * 60)

    except Exception as exc:
        if conn is not None:
            conn.rollback()

        logger.error("Order_items load FAILED: %s", exc)
        sys.exit(1)

    finally:
        if conn is not None:
            conn.close()
            logger.info("PostgreSQL connection closed.")


if __name__ == "__main__":
    main()