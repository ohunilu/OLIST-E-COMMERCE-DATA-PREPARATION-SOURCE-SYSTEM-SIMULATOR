"""
Main entry point for running the Olist reviews pipeline loader.
"""

import sys
from rev_util.rev_db import bulk_load, create_indexes, ensure_target_table, get_connection
from rev_util.rev_config import SCHEMA_NAME, TABLE_NAME, logger
from rev_util.rev_validation import (
    validate_loaded_data,
    validate_orders_foreign_key,
    validate_source_file,
    validate_target_is_empty,
)


def main() -> None:
    logger.info("=" * 60)
    logger.info("Starting Olist reviews data load.")
    logger.info("=" * 60)

    conn = None

    try:
        # Step 1: Source Validation
        df = validate_source_file()
        source_count = len(df)

        # Step 2: Database Connection & Prep
        conn = get_connection()
        ensure_target_table(conn)
        validate_target_is_empty(conn)

        # Step 3: Foreign Key Check Prior to Copy
        validate_orders_foreign_key(conn, df)

        # Step 4: Stream Data via Bulk Copy
        bulk_load(conn, df)

        # Step 5: Post-Load Database Verifications & Indexing
        validate_loaded_data(conn, source_count)
        create_indexes(conn)

        # Step 6: Commit Transaction
        conn.commit()
        logger.info("Reviews transaction committed successfully.")

        logger.info("=" * 60)
        logger.info("Reviews load completed successfully.")
        logger.info("Source records: %s", f"{source_count:,}")
        logger.info("Target table: %s.%s", SCHEMA_NAME, TABLE_NAME)
        logger.info("Target records: %s", f"{source_count:,}")
        logger.info("=" * 60)

    except Exception as exc:
        if conn is not None:
            conn.rollback()

        logger.error("Reviews load FAILED: %s", exc)
        sys.exit(1)

    finally:
        if conn is not None:
            conn.close()
            logger.info("PostgreSQL connection closed.")


if __name__ == "__main__":
    main()