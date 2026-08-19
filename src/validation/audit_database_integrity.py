#!/usr/bin/env python3

"""
Olist E-Commerce Source System Simulator
Database-Level Integrity Audit

Purpose
-------
Audits the PostgreSQL ecommerce_source database after all transformed
Olist datasets have been loaded.

This audit validates:

1. Expected tables exist.
2. Database row counts match transformed CSV row counts.
3. Primary-key uniqueness and nullability.
4. Composite-key uniqueness.
5. Required-field completeness.
6. Foreign-key / referential integrity.
7. Customer signup_date temporal integrity.
8. Order timestamp chronology.
9. Geolocation coordinate validity.
10. Customer -> geolocation ZIP coverage.
11. Product numeric integrity.
12. Payment installment anomalies.
13. Known Olist source-data anomalies.
14. Overall database integrity.

Exit codes
----------
0 = Audit passed
1 = Audit failed
"""

import logging
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2


# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = Path("/app")
SIMULATED_DATA_DIR = BASE_DIR / "simulated_data"

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce_source")
DB_USER = os.getenv("POSTGRES_USER", "olist_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "olist_dev_password")

SCHEMA = "public"


# Expected transformed source files and target tables.
TABLE_FILES = {
    "customers": SIMULATED_DATA_DIR / "customers.csv",
    "orders": SIMULATED_DATA_DIR / "orders.csv",
    "products": SIMULATED_DATA_DIR / "products.csv",
    "sellers": SIMULATED_DATA_DIR / "sellers.csv",
    "payments": SIMULATED_DATA_DIR / "payments.csv",
    "reviews": SIMULATED_DATA_DIR / "reviews.csv",
    "geolocation": SIMULATED_DATA_DIR / "geolocation.csv",
    "order_items": SIMULATED_DATA_DIR / "order_items.csv",
}


# Primary keys.
PRIMARY_KEYS = {
    "customers": ["customer_id"],
    "orders": ["order_id"],
    "products": ["product_id"],
    "sellers": ["seller_id"],
    "geolocation": ["geolocation_zip_code_prefix"],
}


# Composite keys.
COMPOSITE_KEYS = {
    "payments": ["order_id", "payment_sequential"],
    "reviews": ["review_id", "order_id"],
    "order_items": ["order_id", "order_item_id"],
}


# Required fields.
REQUIRED_FIELDS = {
    "customers": [
        "customer_id",
        "customer_unique_id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "address_line_1",
        "city",
        "state",
        "zip_code_prefix",
        "country",
        "signup_date",
    ],
    "orders": [
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
    ],
    "products": [
        "product_id",
    ],
    "sellers": [
        "seller_id",
        "seller_zip_code_prefix",
        "seller_city",
        "seller_state",
    ],
    "payments": [
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_value",
    ],
    "reviews": [
        "review_id",
        "order_id",
    ],
    "geolocation": [
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
    ],
    "order_items": [
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
    ],
}


# Expected referential relationships.
FOREIGN_KEYS = [
    {
        "child_table": "customers",
        "child_column": "zip_code_prefix",
        "parent_table": "geolocation",
        "parent_column": "geolocation_zip_code_prefix",
        "allow_unmatched": True,
        "description": "Customers -> Geolocation ZIP coverage",
    },
    {
        "child_table": "orders",
        "child_column": "customer_id",
        "parent_table": "customers",
        "parent_column": "customer_id",
        "allow_unmatched": False,
        "description": "Orders -> Customers",
    },
    {
        "child_table": "order_items",
        "child_column": "order_id",
        "parent_table": "orders",
        "parent_column": "order_id",
        "allow_unmatched": False,
        "description": "Order items -> Orders",
    },
    {
        "child_table": "order_items",
        "child_column": "product_id",
        "parent_table": "products",
        "parent_column": "product_id",
        "allow_unmatched": False,
        "description": "Order items -> Products",
    },
    {
        "child_table": "order_items",
        "child_column": "seller_id",
        "parent_table": "sellers",
        "parent_column": "seller_id",
        "allow_unmatched": False,
        "description": "Order items -> Sellers",
    },
    {
        "child_table": "payments",
        "child_column": "order_id",
        "parent_table": "orders",
        "parent_column": "order_id",
        "allow_unmatched": False,
        "description": "Payments -> Orders",
    },
    {
        "child_table": "reviews",
        "child_column": "order_id",
        "parent_table": "orders",
        "parent_column": "order_id",
        "allow_unmatched": False,
        "description": "Reviews -> Orders",
    },
]


# Known source-data anomalies deliberately preserved.
KNOWN_ORDER_APPROVED_CARRIER_ANOMALIES = 1359
KNOWN_ORDER_CARRIER_DELIVERY_ANOMALIES = 23
KNOWN_PAYMENT_ZERO_INSTALLMENT_ANOMALIES = 2


# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================================
# AUDIT STATE
# ============================================================================

audit_failures = 0
audit_warnings = 0


def audit_pass(message):
    logger.info("PASS | %s", message)


def audit_warning(message):
    global audit_warnings
    audit_warnings += 1
    logger.warning("WARNING | %s", message)


def audit_fail(message):
    global audit_failures
    audit_failures += 1
    logger.error("FAIL | %s", message)


# ============================================================================
# DATABASE HELPERS
# ============================================================================

def get_connection():
    logger.info(
        "Connecting to PostgreSQL: host=%s port=%s database=%s user=%s",
        DB_HOST,
        DB_PORT,
        DB_NAME,
        DB_USER,
    )

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

    logger.info("PostgreSQL connection established successfully.")

    return conn


def table_exists(cur, table_name):
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_name = %s
        )
        """,
        (SCHEMA, table_name),
    )

    return cur.fetchone()[0]


def get_table_columns(cur, table_name):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (SCHEMA, table_name),
    )

    return [row[0] for row in cur.fetchall()]


def execute_scalar(cur, query, params=None):
    cur.execute(query, params or ())
    return cur.fetchone()[0]


# ============================================================================
# SOURCE FILE AUDIT
# ============================================================================

def load_source_counts():
    """
    Read transformed CSVs only for expected row counts.

    The actual data-integrity audit is performed against PostgreSQL.
    """

    logger.info("Reading transformed source files for expected row counts.")

    source_counts = {}

    for table_name, path in TABLE_FILES.items():

        if not path.exists():
            audit_fail(
                f"Expected transformed source file does not exist: {path}"
            )
            continue

        try:
            df = pd.read_csv(path)
            source_counts[table_name] = len(df)

            logger.info(
                "%s source records: %s",
                table_name,
                f"{len(df):,}",
            )

        except Exception as exc:
            audit_fail(
                f"Unable to read source file for {table_name}: {exc}"
            )

    return source_counts


# ============================================================================
# TABLE EXISTENCE
# ============================================================================

def audit_table_existence(cur):
    logger.info("Starting database table existence audit.")

    for table_name in TABLE_FILES:

        if table_exists(cur, table_name):
            audit_pass(f"Table exists: {SCHEMA}.{table_name}")
        else:
            audit_fail(f"Missing required table: {SCHEMA}.{table_name}")


# ============================================================================
# SCHEMA AUDIT
# ============================================================================

def audit_required_columns(cur):
    logger.info("Starting database schema audit.")

    for table_name, required_columns in REQUIRED_FIELDS.items():

        if not table_exists(cur, table_name):
            continue

        actual_columns = set(get_table_columns(cur, table_name))

        missing = [
            column
            for column in required_columns
            if column not in actual_columns
        ]

        if missing:
            audit_fail(
                f"{table_name} missing required columns: {missing}"
            )
        else:
            audit_pass(
                f"{table_name} required-column validation passed."
            )


# ============================================================================
# ROW COUNT AUDIT
# ============================================================================

def audit_row_counts(cur, source_counts):
    logger.info("Starting database row-count audit.")

    for table_name, expected_count in source_counts.items():

        if not table_exists(cur, table_name):
            continue

        actual_count = execute_scalar(
            cur,
            f'SELECT COUNT(*) FROM "{SCHEMA}"."{table_name}"',
        )

        if actual_count == expected_count:
            audit_pass(
                f"{table_name} row-count validation passed: "
                f"{actual_count:,} records."
            )
        else:
            audit_fail(
                f"{table_name} row-count mismatch: "
                f"source={expected_count:,}, "
                f"database={actual_count:,}."
            )


# ============================================================================
# PRIMARY KEY / COMPOSITE KEY AUDIT
# ============================================================================

def audit_key_integrity(cur):
    logger.info("Starting database key-integrity audit.")

    for table_name, columns in PRIMARY_KEYS.items():

        if not table_exists(cur, table_name):
            continue

        column_list = ", ".join(f'"{column}"' for column in columns)

        null_count = execute_scalar(
            cur,
            f"""
            SELECT COUNT(*)
            FROM "{SCHEMA}"."{table_name}"
            WHERE {" OR ".join(f'"{c}" IS NULL' for c in columns)}
            """,
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
            audit_pass(
                f"{table_name} primary-key validation passed."
            )
        else:
            if null_count > 0:
                audit_fail(
                    f"{table_name} primary key contains "
                    f"{null_count:,} NULL records."
                )

            if duplicate_count > 0:
                audit_fail(
                    f"{table_name} primary key contains "
                    f"{duplicate_count:,} duplicate key groups."
                )

    for table_name, columns in COMPOSITE_KEYS.items():

        if not table_exists(cur, table_name):
            continue

        column_list = ", ".join(f'"{column}"' for column in columns)

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

        null_condition = " OR ".join(
            f'"{column}" IS NULL'
            for column in columns
        )

        null_count = execute_scalar(
            cur,
            f"""
            SELECT COUNT(*)
            FROM "{SCHEMA}"."{table_name}"
            WHERE {null_condition}
            """,
        )

        if null_count == 0 and duplicate_count == 0:
            audit_pass(
                f"{table_name} composite-key validation passed: "
                f"{' + '.join(columns)}."
            )
        else:
            if null_count > 0:
                audit_fail(
                    f"{table_name} composite key contains "
                    f"{null_count:,} NULL records."
                )

            if duplicate_count > 0:
                audit_fail(
                    f"{table_name} composite key contains "
                    f"{duplicate_count:,} duplicate groups."
                )


# ============================================================================
# REQUIRED FIELD AUDIT
# ============================================================================

def audit_required_fields(cur):
    logger.info("Starting required-field completeness audit.")

    for table_name, columns in REQUIRED_FIELDS.items():

        if not table_exists(cur, table_name):
            continue

        table_failures = 0

        for column in columns:

            null_count = execute_scalar(
                cur,
                f"""
                SELECT COUNT(*)
                FROM "{SCHEMA}"."{table_name}"
                WHERE "{column}" IS NULL
                """,
            )

            if null_count > 0:
                audit_fail(
                    f"{table_name}.{column} contains "
                    f"{null_count:,} NULL values."
                )
                table_failures += 1

        if table_failures == 0:
            audit_pass(
                f"{table_name} required-field validation passed."
            )


# ============================================================================
# FOREIGN KEY / REFERENTIAL INTEGRITY
# ============================================================================

def audit_foreign_keys(cur):
    logger.info("Starting database referential-integrity audit.")

    for relationship in FOREIGN_KEYS:

        child = relationship["child_table"]
        child_col = relationship["child_column"]
        parent = relationship["parent_table"]
        parent_col = relationship["parent_column"]
        allow_unmatched = relationship["allow_unmatched"]
        description = relationship["description"]

        if not table_exists(cur, child):
            continue

        if not table_exists(cur, parent):
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
            audit_pass(
                f"{description} validation passed."
            )

        elif allow_unmatched:
            audit_warning(
                f"{description}: {unmatched:,} child records "
                f"have no matching parent record."
            )

        else:
            audit_fail(
                f"{description} failed: "
                f"{unmatched:,} orphan records found."
            )


# ============================================================================
# CUSTOMER TEMPORAL AUDIT
# ============================================================================

def audit_customer_temporal_integrity(cur):
    logger.info(
        "Starting customer signup_date temporal integrity audit."
    )

    null_signup_dates = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.customers
        WHERE signup_date IS NULL
        """,
    )

    if null_signup_dates > 0:
        audit_fail(
            f"Customers contain {null_signup_dates:,} NULL signup_date values."
        )
        return

    audit_pass("Customer signup_date NULL validation passed.")

    invalid_temporal_count = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.customers c
        JOIN public.orders o
          ON c.customer_id = o.customer_id
        WHERE c.signup_date > o.order_purchase_timestamp
        """,
    )

    if invalid_temporal_count > 0:
        audit_fail(
            "Customer temporal integrity failed: "
            f"{invalid_temporal_count:,} orders occur before signup_date."
        )
    else:
        audit_pass(
            "All customer signup dates occur on or before "
            "their corresponding order purchase timestamps."
        )

    derivation_failures = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.customers c
        JOIN (
            SELECT
                customer_id,
                MIN(order_purchase_timestamp) AS first_purchase
            FROM public.orders
            GROUP BY customer_id
        ) o
          ON c.customer_id = o.customer_id
        WHERE c.signup_date <> o.first_purchase
        """,
    )

    if derivation_failures > 0:
        audit_fail(
            "Customer signup_date derivation failed: "
            f"{derivation_failures:,} customers do not have "
            "signup_date equal to MIN(order_purchase_timestamp)."
        )
    else:
        audit_pass(
            "Customer signup_date derivation validation passed."
        )


# ============================================================================
# ORDER TEMPORAL AUDIT
# ============================================================================

def audit_order_temporal_integrity(cur):
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
        audit_pass(
            "Order purchase <= approved validation passed."
        )
    else:
        audit_fail(
            "Order purchase <= approved validation failed: "
            f"{purchase_after_approved:,} records."
        )

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
        audit_warning(
            "Known source chronology anomaly preserved: "
            f"{approved_after_carrier:,} approved/carrier records."
        )
    elif approved_after_carrier == 0:
        audit_pass(
            "No approved/carrier chronology anomalies found."
        )
    else:
        audit_fail(
            "Unexpected approved/carrier anomaly count: "
            f"expected={KNOWN_ORDER_APPROVED_CARRIER_ANOMALIES:,}, "
            f"actual={approved_after_carrier:,}."
        )

    carrier_after_delivery = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.orders
        WHERE order_delivered_carrier_date IS NOT NULL
          AND order_delivered_customer_date IS NOT NULL
          AND order_delivered_carrier_date >
              order_delivered_customer_date
        """,
    )

    if carrier_after_delivery == KNOWN_ORDER_CARRIER_DELIVERY_ANOMALIES:
        audit_warning(
            "Known source chronology anomaly preserved: "
            f"{carrier_after_delivery:,} carrier/delivery records."
        )
    elif carrier_after_delivery == 0:
        audit_pass(
            "No carrier/customer-delivery chronology anomalies found."
        )
    else:
        audit_fail(
            "Unexpected carrier/delivery anomaly count: "
            f"expected={KNOWN_ORDER_CARRIER_DELIVERY_ANOMALIES:,}, "
            f"actual={carrier_after_delivery:,}."
        )


# ============================================================================
# PRODUCT AUDIT
# ============================================================================

def audit_products(cur):
    logger.info("Starting product integrity audit.")

    numeric_columns = [
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
        "product_name_length",
        "product_description_length",
        "product_photos_qty",
    ]

    for column in numeric_columns:

        negative_count = execute_scalar(
            cur,
            f"""
            SELECT COUNT(*)
            FROM public.products
            WHERE "{column}" < 0
            """,
        )

        if negative_count > 0:
            audit_fail(
                f"Products {column} contains "
                f"{negative_count:,} negative values."
            )

    audit_pass("Products non-negative numeric validation passed.")


# ============================================================================
# PAYMENT AUDIT
# ============================================================================

def audit_payments(cur):
    logger.info("Starting payment integrity audit.")

    zero_installments = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.payments
        WHERE payment_installments = 0
        """,
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
        audit_fail(
            "Payment installment validation failed: "
            f"{invalid_installments:,} invalid values."
        )
    else:
        audit_pass(
            "Payment installment range validation passed."
        )

    if zero_installments == KNOWN_PAYMENT_ZERO_INSTALLMENT_ANOMALIES:
        audit_warning(
            "Known source payment anomaly preserved: "
            f"{zero_installments:,} zero-installment records."
        )
    elif zero_installments == 0:
        audit_pass(
            "No zero-installment payment records found."
        )
    else:
        audit_fail(
            "Unexpected zero-installment anomaly count: "
            f"expected={KNOWN_PAYMENT_ZERO_INSTALLMENT_ANOMALIES:,}, "
            f"actual={zero_installments:,}."
        )

    negative_values = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.payments
        WHERE payment_value < 0
        """,
    )

    if negative_values > 0:
        audit_fail(
            f"Payments contain {negative_values:,} negative payment values."
        )
    else:
        audit_pass(
            "Payment value validation passed."
        )


# ============================================================================
# GEOLOCATION AUDIT
# ============================================================================

def audit_geolocation(cur):
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
        audit_fail(
            "Geolocation coordinate validation failed: "
            f"{invalid_coordinates:,} invalid records."
        )
    else:
        audit_pass(
            "Geolocation coordinate validation passed."
        )

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
        audit_warning(
            "Geolocation contains "
            f"{duplicate_zip_groups:,} ZIP prefixes with multiple "
            "geographic observations. This is expected for the Olist "
            "geolocation dataset and is preserved."
        )


# ============================================================================
# CUSTOMER GEOLOCATION COVERAGE
# ============================================================================

def audit_customer_geolocation_coverage(cur):
    logger.info(
        "Starting customer -> geolocation ZIP coverage audit."
    )

    customer_zip_count = execute_scalar(
        cur,
        """
        SELECT COUNT(DISTINCT zip_code_prefix)
        FROM public.customers
        """,
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

    coverage = (
        mapped_zip_count / customer_zip_count * 100
        if customer_zip_count
        else 0
    )

    logger.info(
        "Customer ZIP prefixes: %s",
        f"{customer_zip_count:,}",
    )

    logger.info(
        "Customer ZIP prefixes with geolocation: %s",
        f"{mapped_zip_count:,}",
    )

    logger.info(
        "Customer ZIP prefixes without geolocation: %s",
        f"{missing_zip_count:,}",
    )

    logger.info(
        "Customer ZIP coverage: %.2f%%",
        coverage,
    )

    if coverage == 100:
        audit_pass(
            "Customer -> geolocation ZIP coverage is complete: 100%."
        )
    elif coverage >= 98:
        audit_warning(
            f"Customer -> geolocation ZIP coverage is {coverage:.2f}%. "
            "Incomplete ZIP coverage is consistent with the transformed "
            "source dataset."
        )
    else:
        audit_fail(
            f"Customer -> geolocation ZIP coverage unexpectedly low: "
            f"{coverage:.2f}%."
        )


# ============================================================================
# ORDER ITEMS AUDIT
# ============================================================================

def audit_order_items(cur):
    logger.info("Starting order_items integrity audit.")

    negative_price_count = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.order_items
        WHERE price < 0
        """,
    )

    negative_freight_count = execute_scalar(
        cur,
        """
        SELECT COUNT(*)
        FROM public.order_items
        WHERE freight_value < 0
        """,
    )

    if negative_price_count > 0:
        audit_fail(
            f"Order_items contains {negative_price_count:,} "
            "negative price values."
        )

    if negative_freight_count > 0:
        audit_fail(
            f"Order_items contains {negative_freight_count:,} "
            "negative freight values."
        )

    if negative_price_count == 0 and negative_freight_count == 0:
        audit_pass(
            "Order_items numeric integrity validation passed."
        )


# ============================================================================
# DATABASE CONSTRAINT AUDIT
# ============================================================================

def audit_database_constraints(cur):
    logger.info("Starting PostgreSQL constraint audit.")

    cur.execute(
        """
        SELECT
            tc.table_name,
            tc.constraint_name,
            tc.constraint_type
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = %s
        ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name
        """,
        (SCHEMA,),
    )

    constraints = cur.fetchall()

    if constraints:
        audit_pass(
            f"Database constraint metadata available: "
            f"{len(constraints):,} constraints."
        )
    else:
        audit_warning(
            "No PostgreSQL constraints were discovered in public schema."
        )


# ============================================================================
# DATABASE SUMMARY
# ============================================================================

def log_database_summary(cur):
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

        logger.info(
            "%-15s : %10s records",
            table_name,
            f"{count:,}",
        )


# ============================================================================
# MAIN
# ============================================================================

def main():

    logger.info("=" * 60)
    logger.info(
        "Starting Olist PostgreSQL database-level integrity audit."
    )
    logger.info("=" * 60)

    source_counts = load_source_counts()

    conn = None

    try:

        conn = get_connection()

        with conn.cursor() as cur:

            audit_table_existence(cur)

            audit_required_columns(cur)

            audit_row_counts(
                cur,
                source_counts,
            )

            audit_key_integrity(cur)

            audit_required_fields(cur)

            audit_foreign_keys(cur)

            audit_customer_temporal_integrity(cur)

            audit_order_temporal_integrity(cur)

            audit_products(cur)

            audit_payments(cur)

            audit_geolocation(cur)

            audit_customer_geolocation_coverage(cur)

            audit_order_items(cur)

            audit_database_constraints(cur)

            log_database_summary(cur)

    except Exception as exc:

        audit_fail(
            f"Database audit encountered an unexpected error: {exc}"
        )

    finally:

        if conn is not None:
            conn.close()
            logger.info("PostgreSQL connection closed.")

    logger.info("=" * 60)

    if audit_failures == 0:

        logger.info(
            "DATABASE INTEGRITY AUDIT PASSED."
        )

        logger.info(
            "Warnings: %d | Critical failures: %d",
            audit_warnings,
            audit_failures,
        )

        logger.info(
            "All loaded Olist tables passed database-level "
            "integrity validation."
        )

        logger.info("=" * 60)

        return 0

    logger.error(
        "DATABASE INTEGRITY AUDIT FAILED."
    )

    logger.error(
        "Warnings: %d | Critical failures: %d",
        audit_warnings,
        audit_failures,
    )

    logger.error(
        "The database should NOT be considered ready for "
        "downstream ingestion until the failures are resolved."
    )

    logger.info("=" * 60)

    return 1


if __name__ == "__main__":
    sys.exit(main())