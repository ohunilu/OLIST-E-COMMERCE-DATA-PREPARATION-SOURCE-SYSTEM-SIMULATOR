"""
Configuration settings and logging setup for ETL scripts.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

# Source File Paths
SOURCE_FILE = Path(
    os.getenv(
        "CUSTOMERS_SOURCE_FILE",
        "/app/simulated_data/customers.csv",
    )
)

# Database Settings
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

TARGET_SCHEMA = os.getenv("POSTGRES_SCHEMA", "public")
TARGET_TABLE = "customers"

# Schema Expectations
EXPECTED_COLUMNS = [
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
]

# DDL Statements
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {schema}.{table} (
    customer_id         TEXT PRIMARY KEY,
    customer_unique_id  TEXT NOT NULL,
    first_name          TEXT NOT NULL,
    last_name           TEXT NOT NULL,
    email               TEXT NOT NULL,
    phone               TEXT NOT NULL,
    address_line_1      TEXT NOT NULL,
    city                TEXT NOT NULL,
    state               CHAR(2) NOT NULL,
    zip_code_prefix     INTEGER NOT NULL,
    country             TEXT NOT NULL,
    signup_date         TIMESTAMP NOT NULL
);
"""

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("etl_loader")