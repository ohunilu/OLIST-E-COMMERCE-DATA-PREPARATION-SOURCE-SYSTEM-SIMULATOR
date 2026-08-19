"""
Main entry point for executing the Olist orders loader process.
"""

import sys
from ord_util.ord_db import bulk_load_orders, create_indexes, ensure_schema_and_table, get_connection
from ord_util.ord_config import SCHEMA_NAME, TABLE_NAME, logger
from ord_util.ord_validation import (
    validate_customer_references,
    validate_source_data,
    validate_source_file,
    validate_target,
    validate_target_is_empty,
)


def main() -> None:
    logger.info("=" * 60)
    logger.info("Starting Olist orders data load.")
    logger.info("=" * 60)

    conn = None

    try:
        # Step 1: Source Validation & Timestamp Conversion
        df = validate_source_file()
        validate_source_data(df)
        source_count = len(df)

        # Step 2: Database Setup & Checks
        conn = get_connection()
        ensure_schema_and_table(conn)
        validate_target_is_empty(conn)

        # Step 3: Foreign Key Integrity Verification Prior to Load
        validate_customer_references(conn, df)

        # Step 4: Bulk Ingestion via execute_values
        bulk_load_orders(conn, df)

        # Step 5: Post-Load Target Verification & Indexing
        validate_target(conn, source_count)
        create_indexes(conn)

        # Step 6: Transactional Commit
        conn.commit()
        logger.info("Orders transaction committed successfully.")

        logger.info("=" * 60)
        logger.info("Orders load completed successfully.")
        logger.info("Source records: %s", f"{source_count:,}")
        logger.info("Target table: %s.%s", SCHEMA_NAME, TABLE_NAME)
        logger.info("Target records: %s", f"{source_count:,}")
        logger.info("=" * 60)

    except Exception as exc:
        if conn is not None:
            conn.rollback()
            logger.error("Orders transaction rolled back because of an error.")

        logger.error("Orders load FAILED: %s", exc)
        sys.exit(1)

    finally:
        if conn is not None:
            conn.close()
            logger.info("PostgreSQL connection closed.")


if __name__ == "__main__":
    main()