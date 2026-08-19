"""
Configuration, schema definitions, and constants for the Olist sellers loader.
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
logger = logging.getLogger("sellers_loader")

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SellerLoadError(Exception):
    """Raised when seller validation or loading fails."""

# ---------------------------------------------------------------------------
# File & Database Settings
# ---------------------------------------------------------------------------

SOURCE_FILE = Path("/app/simulated_data/sellers.csv")

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce_source")
DB_USER = os.getenv("POSTGRES_USER", "olist_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")

SCHEMA_NAME = "public"
TABLE_NAME = "sellers"

# ---------------------------------------------------------------------------
# Schema Expectations
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS = [
    "seller_id",
    "seller_zip_code_prefix",
    "seller_city",
    "seller_state",
]

REQUIRED_COLUMNS = [
    "seller_id",
    "seller_zip_code_prefix",
    "seller_city",
    "seller_state",
]

# ---------------------------------------------------------------------------
# Dynamic SQL Queries
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = sql.SQL(
    """
    CREATE TABLE IF NOT EXISTS {}.{} (
        seller_id VARCHAR(64) NOT NULL,
        seller_zip_code_prefix INTEGER NOT NULL,
        seller_city TEXT NOT NULL,
        seller_state VARCHAR(2) NOT NULL,

        CONSTRAINT sellers_pkey
            PRIMARY KEY (seller_id)
    )
    """
).format(
    sql.Identifier(SCHEMA_NAME),
    sql.Identifier(TABLE_NAME),
)

COPY_SQL = sql.SQL(
    """
    COPY {}.{} (
        seller_id,
        seller_zip_code_prefix,
        seller_city,
        seller_state
    )
    FROM STDIN
    WITH (
        FORMAT CSV,
        HEADER TRUE,
        NULL ''
    )
    """
).format(
    sql.Identifier(SCHEMA_NAME),
    sql.Identifier(TABLE_NAME),
)