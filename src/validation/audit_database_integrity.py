"""
Main entrypoint script orchestrating database-level integrity audits for PostgreSQL.
"""

import sys
from cross_audit_util.cross_audit_config import TABLE_FILES, logger
from cross_audit_util.cross_audit_db import connect_database
from cross_audit_util.cross_audit_validators import (
    AuditTracker,
    audit_customer_geolocation_coverage,
    audit_customer_temporal_integrity,
    audit_database_constraints,
    audit_foreign_keys,
    audit_geolocation,
    audit_key_integrity,
    audit_order_items,
    audit_order_temporal_integrity,
    audit_payments,
    audit_products,
    audit_required_columns,
    audit_required_fields,
    audit_row_counts,
    audit_table_existence,
    load_source_counts,
    log_database_summary,
)


def main() -> int:
    logger.info("=" * 60)
    logger.info("Starting Olist PostgreSQL database-level integrity audit.")
    logger.info("=" * 60)

    tracker = AuditTracker()
    source_counts = load_source_counts(tracker)
    conn = None

    try:
        conn = connect_database()

        with conn.cursor() as cur:
            audit_table_existence(cur, tracker)
            audit_required_columns(cur, tracker)
            audit_row_counts(cur, source_counts, tracker)
            audit_key_integrity(cur, tracker)
            audit_required_fields(cur, tracker)
            audit_foreign_keys(cur, tracker)
            audit_customer_temporal_integrity(cur, tracker)
            audit_order_temporal_integrity(cur, tracker)
            audit_products(cur, tracker)
            audit_payments(cur, tracker)
            audit_geolocation(cur, tracker)
            audit_customer_geolocation_coverage(cur, tracker)
            audit_order_items(cur, tracker)
            audit_database_constraints(cur, tracker)

            log_database_summary(cur)

    except Exception as exc:
        tracker.fail_check(f"Database audit encountered an unexpected error: {exc}")

    finally:
        if conn is not None:
            conn.close()
            logger.info("PostgreSQL connection closed.")

    logger.info("=" * 60)

    if tracker.failures == 0:
        logger.info("DATABASE INTEGRITY AUDIT PASSED.")
        logger.info("Warnings: %d | Critical failures: %d", tracker.warnings, tracker.failures)
        logger.info("All loaded Olist tables passed database-level integrity validation.")
        logger.info("=" * 60)
        return 0

    logger.error("DATABASE INTEGRITY AUDIT FAILED.")
    logger.error("Warnings: %d | Critical failures: %d", tracker.warnings, tracker.failures)
    logger.error("The database should NOT be considered ready for downstream ingestion until the failures are resolved.")
    logger.info("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())