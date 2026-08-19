"""
Configuration, schema definitions, and constants for the Olist reviews loader.
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
logger = logging.getLogger("reviews_loader")

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ReviewLoadError(Exception):
    """Raised when review validation or loading fails."""

# ---------------------------------------------------------------------------
# File & Database Settings
# ---------------------------------------------------------------------------

SOURCE_FILE = Path("/app/simulated_data/reviews.csv")

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce_source")
DB_USER = os.getenv("POSTGRES_USER", "olist_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "olist_password")

SCHEMA_NAME = "public"
TABLE_NAME = "reviews"
ORDERS_TABLE = "orders"

# ---------------------------------------------------------------------------
# Schema & Quality Expectations
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS = [
    "review_id",
    "order_id",
    "review_score",
    "review_comment_title",
    "review_comment_message",
    "review_creation_date",
    "review_answer_timestamp",
]

REQUIRED_COLUMNS = [
    "review_id",
    "order_id",
    "review_score",
    "review_creation_date",
    "review_answer_timestamp",
]

MIN_REVIEW_SCORE = 1
MAX_REVIEW_SCORE = 5

# ---------------------------------------------------------------------------
# Dynamic SQL Statements
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = sql.SQL(
    """
    CREATE TABLE IF NOT EXISTS {schema}.{table} (
        review_id TEXT NOT NULL,
        order_id TEXT NOT NULL,
        review_score INTEGER NOT NULL,
        review_comment_title TEXT,
        review_comment_message TEXT,
        review_creation_date TIMESTAMP NOT NULL,
        review_answer_timestamp TIMESTAMP NOT NULL,

        CONSTRAINT reviews_pkey
            PRIMARY KEY (review_id, order_id),

        CONSTRAINT reviews_order_fk
            FOREIGN KEY (order_id)
            REFERENCES {schema}.{orders_table}(order_id),

        CONSTRAINT reviews_score_chk
            CHECK (review_score >= {min_score} AND review_score <= {max_score}),

        CONSTRAINT reviews_chronology_chk
            CHECK (review_creation_date <= review_answer_timestamp)
    )
    """
).format(
    schema=sql.Identifier(SCHEMA_NAME),
    table=sql.Identifier(TABLE_NAME),
    orders_table=sql.Identifier(ORDERS_TABLE),
    min_score=sql.Literal(MIN_REVIEW_SCORE),
    max_score=sql.Literal(MAX_REVIEW_SCORE),
)

COPY_SQL = sql.SQL(
    """
    COPY {schema}.{table} (
        review_id,
        order_id,
        review_score,
        review_comment_title,
        review_comment_message,
        review_creation_date,
        review_answer_timestamp
    )
    FROM STDIN
    WITH CSV
    NULL '\\N'
    """
).format(
    schema=sql.Identifier(SCHEMA_NAME),
    table=sql.Identifier(TABLE_NAME),
)