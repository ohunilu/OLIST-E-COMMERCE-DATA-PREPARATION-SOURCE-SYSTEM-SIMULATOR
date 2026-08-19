"""
Main entry point for executing the Olist sellers loader process.
"""

import sys
from sel_util.sel_db import bulk_load, create_indexes, ensure_target_table, get_connection
from sel_util.sel_config import SCHEMA_NAME, TABLE_NAME, logger
from sel_util.sel_validation import (
    validate_loaded_data,
    validate_source_file,
    validate_target_empty,
)


def main() -> None:
    logger.info("=" * 60)
    logger.info("Starting Olist sellers data load.")
    logger.info("=" * 60)

    conn = None

    try:
        # Step 1: Source Validation
        df = validate_source_file()
        source_count = len(df)

        # Step 2: Database Connection & Table Prep
        conn = get_connection()
        ensure_target_table(conn)
        validate_target_empty(conn)

        # Step 3: Fast Streaming Bulk Ingestion
        bulk_load(conn)

        # Step 4: Target Integrity Checks & Indexing
        validate_loaded_data(conn, source_count)
        create_indexes(conn)

        # Step 5: Transactional Commit
        conn.commit()
        logger.info("Sellers transaction committed successfully.")

        logger.info("=" * 60)
        logger.info("Sellers load completed successfully.")
        logger.info("Source records: %s", f"{source_count:,}")
        logger.info("Target table: %s.%s", SCHEMA_NAME, TABLE_NAME)
        logger.info("Target records: %s", f"{source_count:,}")
        logger.info("=" * 60)

    except Exception as exc:
        if conn is not None:
            conn.rollback()

        logger.error("Sellers load FAILED: %s", exc)
        sys.exit(1)

    finally:
        if conn is not None:
            conn.close()
            logger.info("PostgreSQL connection closed.")


if __name__ == "__main__":
    main()