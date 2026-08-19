"""
Configuration, schema expectations, and SQL queries for the Olist order_items loader.
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
logger = logging.getLogger("order_items_loader")

# ---------------------------------------------------------------------------
# Custom Exception
# ---------------------------------------------------------------------------

class OrderItemLoadError(Exception):
    """Raised when order_items validation, loading, or post-check fails."""

# ---------------------------------------------------------------------------
# Target Database & File Parameters
# ---------------------------------------------------------------------------

SOURCE_FILE = Path("/app/simulated_data/order_items.csv")

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce_source")
DB_USER = os.getenv("POSTGRES_USER", "olist_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "olist_password")

SCHEMA_NAME = "public"
TABLE_NAME = "order_items"
ORDERS_TABLE = "orders"
PRODUCTS_TABLE = "products"
SELLERS_TABLE = "sellers"

# ---------------------------------------------------------------------------
# Schema Specifications
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS = [
    "order_id",
    "order_item_id",
    "product_id",
    "seller_id",
    "shipping_limit_date",
    "price",
    "freight_value",
]

REQUIRED_COLUMNS = EXPECTED_COLUMNS.copy()

NUMERIC_COLUMNS = [
    "order_item_id",
    "price",
    "freight_value",
]

NON_NEGATIVE_COLUMNS = [
    "price",
    "freight_value",
]

# ---------------------------------------------------------------------------
# SQL Queries
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = sql.SQL(
    """
    CREATE TABLE IF NOT EXISTS {schema}.{table} (
        order_id TEXT NOT NULL,
        order_item_id INTEGER NOT NULL,
        product_id TEXT NOT NULL,
        seller_id TEXT NOT NULL,
        shipping_limit_date TIMESTAMP NOT NULL,
        price NUMERIC(12, 2) NOT NULL,
        freight_value NUMERIC(12, 2) NOT NULL,

        CONSTRAINT order_items_pk
            PRIMARY KEY (order_id, order_item_id),

        CONSTRAINT order_items_order_fk
            FOREIGN KEY (order_id)
            REFERENCES {schema}.{orders_table} (order_id),

        CONSTRAINT order_items_product_fk
            FOREIGN KEY (product_id)
            REFERENCES {schema}.{products_table} (product_id),

        CONSTRAINT order_items_seller_fk
            FOREIGN KEY (seller_id)
            REFERENCES {schema}.{sellers_table} (seller_id),

        CONSTRAINT order_items_price_nonnegative
            CHECK (price >= 0),

        CONSTRAINT order_items_freight_nonnegative
            CHECK (freight_value >= 0)
    )
    """
).format(
    schema=sql.Identifier(SCHEMA_NAME),
    table=sql.Identifier(TABLE_NAME),
    orders_table=sql.Identifier(ORDERS_TABLE),
    products_table=sql.Identifier(PRODUCTS_TABLE),
    sellers_table=sql.Identifier(SELLERS_TABLE),
)

COPY_SQL = sql.SQL(
    """
    COPY {schema}.{table} (
        order_id,
        order_item_id,
        product_id,
        seller_id,
        shipping_limit_date,
        price,
        freight_value
    )
    FROM STDIN
    WITH (
        FORMAT CSV,
        NULL '\\N'
    )
    """
).format(
    schema=sql.Identifier(SCHEMA_NAME),
    table=sql.Identifier(TABLE_NAME),
)