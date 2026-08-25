"""
Configuration settings, lookup metadata, and exception definitions for DB integrity auditing.
"""

import logging
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("database_integrity_audit")

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DatabaseAuditError(Exception):
    """Raised for structural or operational database audit execution errors."""

# ---------------------------------------------------------------------------
# System & Path Parameters
# ---------------------------------------------------------------------------

BASE_DIR = Path("/app")
SIMULATED_DATA_DIR = BASE_DIR / "simulated_data"

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce_source")
DB_USER = os.getenv("POSTGRES_USER", "olist_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "olist_dev_password")

SCHEMA = "public"

# ---------------------------------------------------------------------------
# Entity Expectations & Schema Mappings
# ---------------------------------------------------------------------------

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

PRIMARY_KEYS = {
    "customers": ["customer_id"],
    "orders": ["order_id"],
    "products": ["product_id"],
    "sellers": ["seller_id"],
}

COMPOSITE_KEYS = {
    "payments": ["order_id", "payment_sequential"],
    "reviews": ["review_id", "order_id"],
    "order_items": ["order_id", "order_item_id"],
}

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

# Known source data anomalies deliberately preserved
KNOWN_ORDER_APPROVED_CARRIER_ANOMALIES = 1359
KNOWN_ORDER_CARRIER_DELIVERY_ANOMALIES = 23
KNOWN_PAYMENT_ZERO_INSTALLMENT_ANOMALIES = 2