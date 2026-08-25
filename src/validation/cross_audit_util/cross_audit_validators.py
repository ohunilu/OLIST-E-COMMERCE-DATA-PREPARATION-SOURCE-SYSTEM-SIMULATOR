"""
Data integrity check routines and validation state management.
"""

from typing import Dict
import pandas as pd
from psycopg2 import sql
from cross_audit_util.cross_audit_config import (
    COMPOSITE_KEYS,
    FOREIGN_KEYS,
    KNOWN_ORDER_APPROVED_CARRIER_ANOMALIES,
    KNOWN_ORDER_CARRIER_DELIVERY_ANOMALIES,
    KNOWN_PAYMENT_ZERO_INSTALLMENT_ANOMALIES,
    PRIMARY_KEYS,
    REQUIRED_FIELDS,
    SCHEMA,
    TABLE_FILES,
    logger,
)
from cross_audit_util.cross_audit_db import execute_scalar, get_table_columns, table_exists


class AuditTracker:
    """Tracks audit pass, warning, and failure metrics."""

    def __init__(self):
        self.failures = 0
        self.warnings = 0

    def pass_check(self, message: str) -> None:
        logger.info("PASS | %s", message)

    def warn_check(self, message: str) -> None:
        self.warnings += 1
        logger.warning("WARNING | %s", message)

    def fail_check(self, message: str) -> None:
        self.failures += 1
        logger.error("FAIL | %s", message)


def load_source_counts(tracker: AuditTracker) -> Dict[str, int]:
    """Inspect transformed source CSV row counts to set expectations."""
    logger.info("Reading transformed source files for expected row counts.")
    source_counts = {}

    for table_name, path in TABLE_FILES.items():
        if not path.exists():
            tracker.fail_check(f"Expected transformed source file does not exist: {path}")
            continue

        try:
            df = pd.read_csv(path)
            source_counts[table_name] = len(df)
            logger.info("%s source records: %s", table_name, f"{len(df):,}")
        except Exception as exc:
            tracker.fail_check(f"Unable to read source file for {table_name}: {exc}")

    return source_counts


def audit_table_existence(cur, tracker: AuditTracker) -> None:
    """Verify presence of required Olist tables."""
    logger.info("Starting database table existence audit.")
    for table_name in TABLE_FILES:
        if table_exists(cur, table_name):
            tracker.pass_check(f"Table exists: {SCHEMA}.{table_name}")
        else:
            tracker.fail_check(f"Missing required table: {SCHEMA}.{table_name}")


def audit_required_columns(cur, tracker: AuditTracker) -> None:
    """Ensure expected schema columns are registered on existing tables."""
    logger.info("Starting database schema audit.")
    for table_name, required_columns in REQUIRED_FIELDS.items():
        if not table_exists(cur, table_name):
            continue

        actual_columns = set(get_table_columns(cur, table_name))
        missing = [col for col in required_columns if col not in actual_columns]

        if missing:
            tracker.fail_check(f"{table_name} missing required columns: {missing}")
        else:
            tracker.pass_check(f"{table_name} required-column validation passed.")


def audit_row_counts(cur, source_counts: Dict[str, int], tracker: AuditTracker) -> None:
    """Validate database row counts match transformed source CSV counts."""
    logger.info("Starting database row-count audit.")
    for table_name, expected_count in source_counts.items():
        if not table_exists(cur, table_name):
            continue

        actual_count = execute_scalar(
            cur,
            f'SELECT COUNT(*) FROM "{SCHEMA}"."{table_name}"',
        )

        if actual_count == expected_count:
            tracker.pass_check(
                f"{table_name} row-count validation passed: {actual_count:,} records."
            )
        else:
            tracker.fail_check(
                f"{table_name} row-count mismatch: source={expected_count:,}, database={actual_count:,}."
            )


def audit_key_integrity(cur, tracker: AuditTracker) -> None:
    """Audit primary and composite keys for duplicates and null values."""
    logger.info("Starting database key-integrity audit.")

    for table_name, columns in PRIMARY_KEYS.items():
        if not table_exists(cur, table_name):
            continue

        column_list = ", ".join(f'"{column}"' for column in columns)
        null_cond = " OR ".join(f'"{c}" IS NULL' for c in columns)

        null_count = execute_scalar(
            cur,
            f'SELECT COUNT(*) FROM "{SCHEMA}"."{table_name}" WHERE {null_cond}',
        )

        duplicate_count = execute_scalar(
            cur,
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT {column_list}
                FROM "{SCHEMA}"."{table_name}"
                GROUP BY {column_list}
                HAVING COUNT(*) > 1
            ) duplicates
            """,
        )

        if null_count == 0 and duplicate_count == 0:
            tracker.pass_check(f"{table_name} primary-key validation passed.")
        else:
            if null_count > 0:
                tracker.fail_check(f"{table_name} primary key contains {null_count:,} NULL records.")
            if duplicate_count > 0:
                tracker.fail_check(f"{table_name} primary key contains {duplicate_count:,} duplicate key groups.")

    for table_name, columns in COMPOSITE_KEYS.items():
        if not table_exists(cur, table_name):
            continue

        column_list = ", ".join(f'"{column}"' for column in columns)
        null_cond = " OR ".join(f'"{column}" IS NULL' for column in columns)

        duplicate_count = execute_scalar(
            cur,
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT {column_list}
                FROM "{SCHEMA}"."{table_name}"
                GROUP BY {column_list}
                HAVING COUNT(*) > 1
            ) duplicates
            """,
        )

        null_count = execute_scalar(
            cur,
            f'SELECT COUNT(*) FROM "{SCHEMA}"."{table_name}" WHERE {null_cond}',
        )

        if null_count == 0 and duplicate_count == 0:
            tracker.pass_check(f"{table_name} composite-key validation passed: {' + '.join(columns)}.")
        else:
            if null_count > 0:
                tracker.fail_check(f"{table_name} composite key contains {null_count:,} NULL records.")
            if duplicate_count > 0:
                tracker.fail_check(f"{table_name} composite key contains {duplicate_count:,} duplicate groups.")


def audit_required_fields(cur, tracker: AuditTracker) -> None:
    """Verify non-null constraints across required columns."""
    logger.info("Starting required-field completeness audit.")
    for table_name, columns in REQUIRED_FIELDS.items():
        if not table_exists(cur, table_name):
            continue

        table_failures = 0
        for column in columns:
            null_count = execute_scalar(
                cur,
                f'SELECT COUNT(*) FROM "{SCHEMA}"."{table_name}" WHERE "{column}" IS NULL',
            )
            if null_count > 0:
                tracker.fail_check(f"{table_name}.{column} contains {null_count:,} NULL values.")
                table_failures += 1

        if table_failures == 0:
            tracker.pass_check(f"{table_name} required-field validation passed.")


def audit_foreign_keys(cur, tracker: AuditTracker) -> None:
    """Audit foreign key relationships and orphan records."""
    logger.info("Starting database referential-integrity audit.")
    for relationship in FOREIGN_KEYS:
        child = relationship["child_table"]
        child_col = relationship["child_column"]
        parent = relationship["parent_table"]
        parent_col = relationship["parent_column"]
        allow_unmatched = relationship["allow_unmatched"]
        description = relationship["description"]

        if not table_exists(cur, child) or not table_exists(cur, parent):
            continue

        unmatched = execute_scalar(
            cur,
            f"""
            SELECT COUNT(*)
            FROM "{SCHEMA}"."{child}" c
            LEFT JOIN "{SCHEMA}"."{parent}" p
              ON c."{child_col}" = p."{parent_col}"
            WHERE c."{child_col}" IS NOT NULL
              AND p."{parent_col}" IS NULL
            """,
        )

        if unmatched == 0:
            tracker.pass_check(f"{description} validation passed.")
        elif allow_unmatched:
            tracker.warn_check(f"{description}: {unmatched:,} child records have no matching parent record.")
        else:
            tracker.fail_check(f"{description} failed: {unmatched:,} orphan records found.")


def audit_customer_temporal_integrity(cur, tracker: AuditTracker) -> None:
    """Audit signup timestamps relative to customer order timestamps."""
    logger.info("Starting customer signup_date temporal integrity audit.")

    null_signup_dates = execute_scalar(
        cur,
        "SELECT COUNT(*) FROM public.customers WHERE signup_date IS NULL",
    )

    if null_signup_dates > 0:
        tracker.fail_check(f"Customers contain {null_signup_dates:,} NULL signup_date values.")
        return

    tracker.pass_check("Customer signup_date NULL validation passed.")

    invalid_temporal_count = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.customers c
        JOIN public.orders o ON c.customer_id = o.customer_id
        WHERE c.signup_date > o.order_purchase_timestamp
        """,
    )

    if invalid_temporal_count > 0:
        tracker.fail_check(f"Customer temporal integrity failed: {invalid_temporal_count:,} orders occur before signup_date.")
    else:
        tracker.pass_check("All customer signup dates occur on or before their corresponding order purchase timestamps.")

    derivation_failures = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.customers c
        JOIN (
            SELECT customer_id, MIN(order_purchase_timestamp) AS first_purchase
            FROM public.orders
            GROUP BY customer_id
        ) o ON c.customer_id = o.customer_id
        WHERE c.signup_date <> o.first_purchase
        """,
    )

    if derivation_failures > 0:
        tracker.fail_check(
            f"Customer signup_date derivation failed: {derivation_failures:,} customers do not have signup_date equal to MIN(order_purchase_timestamp)."
        )
    else:
        tracker.pass_check("Customer signup_date derivation validation passed.")


def audit_order_temporal_integrity(cur, tracker: AuditTracker) -> None:
    """Audit order chronological sequence and record expected historical anomalies."""
    logger.info("Starting order temporal integrity audit.")

    purchase_after_approved = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.orders
        WHERE order_approved_at IS NOT NULL
          AND order_purchase_timestamp > order_approved_at
        """,
    )

    if purchase_after_approved == 0:
        tracker.pass_check("Order purchase <= approved validation passed.")
    else:
        tracker.fail_check(f"Order purchase <= approved validation failed: {purchase_after_approved:,} records.")

    approved_after_carrier = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.orders
        WHERE order_approved_at IS NOT NULL
          AND order_delivered_carrier_date IS NOT NULL
          AND order_approved_at > order_delivered_carrier_date
        """,
    )

    if approved_after_carrier == KNOWN_ORDER_APPROVED_CARRIER_ANOMALIES:
        tracker.warn_check(f"Known source chronology anomaly preserved: {approved_after_carrier:,} approved/carrier records.")
    elif approved_after_carrier == 0:
        tracker.pass_check("No approved/carrier chronology anomalies found.")
    else:
        tracker.fail_check(
            f"Unexpected approved/carrier anomaly count: expected={KNOWN_ORDER_APPROVED_CARRIER_ANOMALIES:,}, actual={approved_after_carrier:,}."
        )

    carrier_after_delivery = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.orders
        WHERE order_delivered_carrier_date IS NOT NULL
          AND order_delivered_customer_date IS NOT NULL
          AND order_delivered_carrier_date > order_delivered_customer_date
        """,
    )

    if carrier_after_delivery == KNOWN_ORDER_CARRIER_DELIVERY_ANOMALIES:
        tracker.warn_check(f"Known source chronology anomaly preserved: {carrier_after_delivery:,} carrier/delivery records.")
    elif carrier_after_delivery == 0:
        tracker.pass_check("No carrier/customer-delivery chronology anomalies found.")
    else:
        tracker.fail_check(
            f"Unexpected carrier/delivery anomaly count: expected={KNOWN_ORDER_CARRIER_DELIVERY_ANOMALIES:,}, actual={carrier_after_delivery:,}."
        )


def audit_products(cur, tracker: AuditTracker) -> None:
    """Validate numeric product bounds."""
    logger.info("Starting product integrity audit.")
    numeric_columns = [
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
    ]

    for column in numeric_columns:
        negative_count = execute_scalar(
            cur,
            f'SELECT COUNT(*) FROM public.products WHERE "{column}" < 0',
        )
        if negative_count > 0:
            tracker.fail_check(f"Products {column} contains {negative_count:,} negative values.")

    tracker.pass_check("Products non-negative numeric validation passed.")


def audit_payments(cur, tracker: AuditTracker) -> None:
    """Validate payment value bounds and installment counts."""
    logger.info("Starting payment integrity audit.")

    zero_installments = execute_scalar(
        cur,
        "SELECT COUNT(*) FROM public.payments WHERE payment_installments = 0",
    )

    invalid_installments = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.payments
        WHERE payment_installments < 0
           OR payment_installments > 24
        """,
    )

    if invalid_installments > 0:
        tracker.fail_check(f"Payment installment validation failed: {invalid_installments:,} invalid values.")
    else:
        tracker.pass_check("Payment installment range validation passed.")

    if zero_installments == KNOWN_PAYMENT_ZERO_INSTALLMENT_ANOMALIES:
        tracker.warn_check(f"Known source payment anomaly preserved: {zero_installments:,} zero-installment records.")
    elif zero_installments == 0:
        tracker.pass_check("No zero-installment payment records found.")
    else:
        tracker.fail_check(
            f"Unexpected zero-installment anomaly count: expected={KNOWN_PAYMENT_ZERO_INSTALLMENT_ANOMALIES:,}, actual={zero_installments:,}."
        )

    negative_values = execute_scalar(
        cur,
        "SELECT COUNT(*) FROM public.payments WHERE payment_value < 0",
    )

    if negative_values > 0:
        tracker.fail_check(f"Payments contain {negative_values:,} negative payment values.")
    else:
        tracker.pass_check("Payment value validation passed.")


def audit_geolocation(cur, tracker: AuditTracker) -> None:
    """Validate latitude/longitude boundary bounds and ZIP duplicate expectations."""
    logger.info("Starting geolocation integrity audit.")

    invalid_coordinates = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.geolocation
        WHERE geolocation_lat < -90
           OR geolocation_lat > 90
           OR geolocation_lng < -180
           OR geolocation_lng > 180
        """,
    )

    if invalid_coordinates > 0:
        tracker.fail_check(f"Geolocation coordinate validation failed: {invalid_coordinates:,} invalid records.")
    else:
        tracker.pass_check("Geolocation coordinate validation passed.")

    duplicate_zip_groups = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM (
            SELECT geolocation_zip_code_prefix
            FROM public.geolocation
            GROUP BY geolocation_zip_code_prefix
            HAVING COUNT(*) > 1
        ) d
        """,
    )

    if duplicate_zip_groups > 0:
        tracker.warn_check(
            f"Geolocation contains {duplicate_zip_groups:,} ZIP prefixes with multiple geographic observations. This is expected for the Olist geolocation dataset and is preserved."
        )


def audit_customer_geolocation_coverage(cur, tracker: AuditTracker) -> None:
    """Evaluate percentage of customer ZIP prefixes covered by geolocation table."""
    logger.info("Starting customer -> geolocation ZIP coverage audit.")

    customer_zip_count = execute_scalar(
        cur,
        "SELECT COUNT(DISTINCT zip_code_prefix) FROM public.customers",
    )

    mapped_zip_count = execute_scalar(
        cur,
        """
        SELECT COUNT(DISTINCT c.zip_code_prefix)
        FROM public.customers c
        JOIN public.geolocation g
          ON c.zip_code_prefix = g.geolocation_zip_code_prefix
        """,
    )

    missing_zip_count = customer_zip_count - mapped_zip_count
    coverage = (mapped_zip_count / customer_zip_count * 100) if customer_zip_count else 0

    logger.info("Customer ZIP prefixes: %s", f"{customer_zip_count:,}")
    logger.info("Customer ZIP prefixes with geolocation: %s", f"{mapped_zip_count:,}")
    logger.info("Customer ZIP prefixes without geolocation: %s", f"{missing_zip_count:,}")
    logger.info("Customer ZIP coverage: %.2f%%", coverage)

    if coverage == 100:
        tracker.pass_check("Customer -> geolocation ZIP coverage is complete: 100%.")
    elif coverage >= 98:
        tracker.warn_check(
            f"Customer -> geolocation ZIP coverage is {coverage:.2f}%. Incomplete ZIP coverage is consistent with the transformed source dataset."
        )
    else:
        tracker.fail_check(f"Customer -> geolocation ZIP coverage unexpectedly low: {coverage:.2f}%.")


def audit_order_items(cur, tracker: AuditTracker) -> None:
    """Validate price and freight values in order_items."""
    logger.info("Starting order_items integrity audit.")

    negative_price_count = execute_scalar(
        cur,
        "SELECT COUNT(*) FROM public.order_items WHERE price < 0",
    )

    negative_freight_count = execute_scalar(
        cur,
        "SELECT COUNT(*) FROM public.order_items WHERE freight_value < 0",
    )

    if negative_price_count > 0:
        tracker.fail_check(f"Order_items contains {negative_price_count:,} negative price values.")

    if negative_freight_count > 0:
        tracker.fail_check(f"Order_items contains {negative_freight_count:,} negative freight values.")

    if negative_price_count == 0 and negative_freight_count == 0:
        tracker.pass_check("Order_items numeric integrity validation passed.")


def audit_database_constraints(cur, tracker: AuditTracker) -> None:
    """Audit PostgreSQL table constraints in public schema."""
    logger.info("Starting PostgreSQL constraint audit.")

    cur.execute(
        """
        SELECT tc.table_name, tc.constraint_name, tc.constraint_type
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = %s
        ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name
        """,
        (SCHEMA,),
    )

    constraints = cur.fetchall()

    if constraints:
        tracker.pass_check(f"Database constraint metadata available: {len(constraints):,} constraints.")
    else:
        tracker.warn_check("No PostgreSQL constraints were discovered in public schema.")


def log_database_summary(cur) -> None:
    """Log record counts across all target tables."""
    logger.info("=" * 60)
    logger.info("DATABASE AUDIT SUMMARY")
    logger.info("=" * 60)

    for table_name in TABLE_FILES:
        if not table_exists(cur, table_name):
            continue

        count = execute_scalar(
            cur,
            f'SELECT COUNT(*) FROM "{SCHEMA}"."{table_name}"',
        )

        logger.info("%-15s : %10s records", table_name, f"{count:,}")