"""
Main execution module for loading Olist products data into PostgreSQL.
"""

import sys
from pro_util.pro_db import bulk_load_products, connect_postgres, create_indexes, ensure_target_table
from pro_util.pro_config import logger
from pro_util.pro_validation import (
    validate_source_data,
    validate_source_file,
    validate_target,
    validate_target_empty,
)


def main() -> None:
    logger.info("=" * 60)
    logger.info("Starting Olist products data load.")
    logger.info("=" * 60)

    conn = None

    try:
        # Step 1: Validate source file and contents
        df = validate_source_file()
        validate_source_data(df)
        source_count = len(df)

        # Step 2: Establish database connection and prepare schema
        conn = connect_postgres()
        ensure_target_table(conn)
        validate_target_empty(conn)

        # Step 3: Perform bulk loading
        bulk_load_products(conn, df)

        # Step 4: Validate target state and build indexes
        validate_target(conn, source_count)
        create_indexes(conn)

        # Step 5: Commit transaction
        conn.commit()
        logger.info("Products transaction committed successfully.")

        logger.info("=" * 60)
        logger.info("Products load completed successfully.")
        logger.info("Source records: %s", f"{source_count:,}")
        logger.info("Target table: public.products")
        logger.info("Target records: %s", f"{source_count:,}")
        logger.info("=" * 60)

    except Exception as exc:
        if conn is not None:
            conn.rollback()

        logger.error("Products load FAILED: %s", exc)
        sys.exit(1)

    finally:
        if conn is not None:
            conn.close()
            logger.info("PostgreSQL connection closed.")


if __name__ == "__main__":
    main()