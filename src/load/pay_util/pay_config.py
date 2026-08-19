"""
Configuration settings and logging setup for the payments loader.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

# Source and Target Settings
SOURCE_FILE = Path(
    os.getenv(
        "PAYMENTS_SOURCE_FILE",
        "/app/simulated_data/payments.csv",
    )
)

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce_source")
DB_USER = os.getenv("POSTGRES_USER", "olist_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "olist_password")

SCHEMA_NAME = "public"
TABLE_NAME = "payments"
ORDERS_TABLE = "orders"

# Expected Schema Definitions
EXPECTED_COLUMNS = [
    "order_id",
    "payment_sequential",
    "payment_type",
    "payment_installments",
    "payment_value",
]

PAYMENT_TYPES = {
    "credit_card",
    "boleto",
    "voucher",
    "debit_card",
    "not_defined",
}

MAX_INSTALLMENTS = 24

# Known source anomaly:
# Two credit-card records have payment_installments = 0.
KNOWN_ZERO_INSTALLMENT_COUNT = 2

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)