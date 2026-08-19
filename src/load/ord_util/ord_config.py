"""
Configuration, schema definitions, and constants for the Olist orders loader.
"""

import logging
import os
from pathlib import Path
from psycopg2 import sql

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("orders_loader")

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OrderLoadError(Exception):
    """Raised when order validation or loading fails."""

# ---------------------------------------------------------------------------
# File & Database Settings
# ---------------------------------------------------------------------------

SOURCE_FILE = Path("/app/simulated_data/orders.csv")

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce_source")
DB_USER = os.getenv("POSTGRES_USER", "olist_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")

SCHEMA_NAME = "public"
TABLE_NAME = "orders"
CUSTOMERS_TABLE = "customers"

# ---------------------------------------------------------------------------
# Schema Expectations
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS = [
    "order_id",
    "customer_id",
    "order_status",
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]

REQUIRED_COLUMNS = [
    "order_id",
    "customer_id",
    "order_status",
    "order_purchase_timestamp",
]

TIMESTAMP_COLUMNS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]

# ---------------------------------------------------------------------------
# Dynamic SQL Statements
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = sql.SQL(
    """
    CREATE TABLE IF NOT EXISTS {schema}.{table} (
        order_id VARCHAR(32) PRIMARY KEY,
        customer_id VARCHAR(32) NOT NULL,
        order_status VARCHAR(50) NOT NULL,
        order_purchase_timestamp TIMESTAMP NOT NULL,
        order_approved_at TIMESTAMP NULL,
        order_delivered_carrier_date TIMESTAMP NULL,
        order_delivered_customer_date TIMESTAMP NULL,
        order_estimated_delivery_date TIMESTAMP NULL,

        CONSTRAINT fk_orders_customer
            FOREIGN KEY (customer_id)
            REFERENCES {schema}.{customers_table} (customer_id)
    )
    """
).format(
    schema=sql.Identifier(SCHEMA_NAME),
    table=sql.Identifier(TABLE_NAME),
    customers_table=sql.Identifier(CUSTOMERS_TABLE),
)

INSERT_SQL = sql.SQL(
    """
    INSERT INTO {schema}.{table} (
        order_id,
        customer_id,
        order_status,
        order_purchase_timestamp,
        order_approved_at,
        order_delivered_carrier_date,
        order_delivered_customer_date,
        order_estimated_delivery_date
    )
    VALUES %s
    """
).format(
    schema=sql.Identifier(SCHEMA_NAME),
    table=sql.Identifier(TABLE_NAME),
)