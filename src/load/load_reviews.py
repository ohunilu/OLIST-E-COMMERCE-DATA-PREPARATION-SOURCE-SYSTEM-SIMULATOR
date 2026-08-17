"""
Load transformed Olist review data into PostgreSQL.

Source:
    /app/simulated_data/reviews.csv

Target:
    public.reviews

Review uniqueness model:
    review_id alone is NOT unique.
    review_id + order_id is the composite primary key.
"""

import logging
import os
import sys
from io import StringIO

import pandas as pd
import psycopg2
from psycopg2 import sql


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_FILE = "/app/simulated_data/reviews.csv"

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce_source")
DB_USER = os.getenv("POSTGRES_USER", "olist_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "olist_password")

SCHEMA_NAME = "public"
TABLE_NAME = "reviews"
ORDERS_TABLE = "orders"

EXPECTED_COLUMNS = [
    "review_id",
    "order_id",
    "review_score",
    "review_comment_title",
    "review_comment_message",
    "review_creation_date",
    "review_answer_timestamp",
]

MIN_REVIEW_SCORE = 1
MAX_REVIEW_SCORE = 5


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

def get_connection():
    """Create PostgreSQL connection."""

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

    logger.info(
        "PostgreSQL connection established successfully."
    )

    return conn


def ensure_schema(conn):
    """Ensure target schema exists."""

    logger.info(
        "Ensuring PostgreSQL schema exists: %s",
        SCHEMA_NAME,
    )

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                "CREATE SCHEMA IF NOT EXISTS {}"
            ).format(
                sql.Identifier(SCHEMA_NAME)
            )
        )

    conn.commit()


# ---------------------------------------------------------------------------
# Source validation
# ---------------------------------------------------------------------------

def validate_source_file():

    logger.info(
        "Reading reviews source file: %s",
        SOURCE_FILE,
    )

    if not os.path.exists(SOURCE_FILE):
        raise FileNotFoundError(
            f"Reviews source file not found: {SOURCE_FILE}"
        )

    logger.info(
        "Reviews source file validation passed."
    )

    df = pd.read_csv(SOURCE_FILE)

    # ------------------------------------------------------------------
    # Schema validation
    # ------------------------------------------------------------------

    actual_columns = df.columns.tolist()

    missing_columns = [
        column
        for column in EXPECTED_COLUMNS
        if column not in actual_columns
    ]

    unexpected_columns = [
        column
        for column in actual_columns
        if column not in EXPECTED_COLUMNS
    ]

    if missing_columns or unexpected_columns:
        raise ValueError(
            "Reviews source schema mismatch. "
            f"Missing columns: {missing_columns}; "
            f"Unexpected columns: {unexpected_columns}"
        )

    logger.info(
        "Reviews source schema validation passed."
    )

    logger.info(
        "Source records available for loading: %s",
        len(df),
    )

    # ------------------------------------------------------------------
    # Required-field validation
    # ------------------------------------------------------------------

    required_columns = [
        "review_id",
        "order_id",
        "review_score",
        "review_creation_date",
        "review_answer_timestamp",
    ]

    null_counts = df[required_columns].isna().sum()

    invalid_nulls = null_counts[null_counts > 0]

    if not invalid_nulls.empty:
        raise ValueError(
            "Reviews required-field validation failed: "
            f"{invalid_nulls.to_dict()}"
        )

    logger.info(
        "Reviews required-field validation passed."
    )

    # ------------------------------------------------------------------
    # Composite-key validation
    # ------------------------------------------------------------------

    duplicate_composite_keys = df.duplicated(
        ["review_id", "order_id"]
    ).sum()

    if duplicate_composite_keys > 0:
        raise ValueError(
            "Review composite-key validation failed: "
            f"{duplicate_composite_keys} duplicate "
            "review_id + order_id records."
        )

    logger.info(
        "Review composite-key validation passed."
    )

    # ------------------------------------------------------------------
    # Review ID uniqueness model
    # ------------------------------------------------------------------

    duplicate_review_ids = (
        df["review_id"].duplicated().sum()
    )

    if duplicate_review_ids > 0:

        logger.info(
            "Review uniqueness model validated: "
            "review_id alone is non-unique; "
            "review_id + order_id is unique."
        )

    else:

        logger.info(
            "Review ID validation passed: "
            "review_id values are unique."
        )

    # ------------------------------------------------------------------
    # Review score validation
    # ------------------------------------------------------------------

    invalid_scores = df[
        (df["review_score"] < MIN_REVIEW_SCORE)
        | (df["review_score"] > MAX_REVIEW_SCORE)
    ]

    if len(invalid_scores) > 0:
        raise ValueError(
            "Review score validation failed: "
            f"{len(invalid_scores)} invalid values. "
            f"Expected range: "
            f"{MIN_REVIEW_SCORE}-{MAX_REVIEW_SCORE}."
        )

    logger.info(
        "Review score validation passed."
    )

    logger.info(
        "Review score distribution: %s",
        df["review_score"].value_counts()
        .sort_index()
        .to_dict(),
    )

    # ------------------------------------------------------------------
    # Timestamp parsing
    # ------------------------------------------------------------------

    creation_ts = pd.to_datetime(
        df["review_creation_date"],
        errors="coerce",
    )

    answer_ts = pd.to_datetime(
        df["review_answer_timestamp"],
        errors="coerce",
    )

    if creation_ts.isna().any():
        invalid_count = creation_ts.isna().sum()

        raise ValueError(
            "Review creation timestamp validation failed: "
            f"{invalid_count} invalid timestamps."
        )

    if answer_ts.isna().any():
        invalid_count = answer_ts.isna().sum()

        raise ValueError(
            "Review answer timestamp validation failed: "
            f"{invalid_count} invalid timestamps."
        )

    logger.info(
        "Review timestamp parsing validation passed."
    )

    # ------------------------------------------------------------------
    # Review chronology
    # ------------------------------------------------------------------

    chronology_violations = (
        creation_ts > answer_ts
    ).sum()

    if chronology_violations > 0:
        raise ValueError(
            "Review chronology validation failed: "
            f"review_creation_date > "
            f"review_answer_timestamp in "
            f"{chronology_violations} records."
        )

    logger.info(
        "Review chronology validation passed: "
        "creation <= answer."
    )

    # ------------------------------------------------------------------
    # Review timestamp ranges
    # ------------------------------------------------------------------

    logger.info(
        "Review creation timestamp range: %s to %s",
        creation_ts.min(),
        creation_ts.max(),
    )

    logger.info(
        "Review answer timestamp range: %s to %s",
        answer_ts.min(),
        answer_ts.max(),
    )

    return df


# ---------------------------------------------------------------------------
# Target table
# ---------------------------------------------------------------------------

def ensure_target_table(conn):

    logger.info(
        "Ensuring target table exists: %s.%s",
        SCHEMA_NAME,
        TABLE_NAME,
    )

    create_sql = f"""
        CREATE TABLE IF NOT EXISTS
        {SCHEMA_NAME}.{TABLE_NAME} (

            review_id TEXT NOT NULL,

            order_id TEXT NOT NULL,

            review_score INTEGER NOT NULL,

            review_comment_title TEXT,

            review_comment_message TEXT,

            review_creation_date TIMESTAMP NOT NULL,

            review_answer_timestamp TIMESTAMP NOT NULL,

            CONSTRAINT reviews_pkey
                PRIMARY KEY (
                    review_id,
                    order_id
                ),

            CONSTRAINT reviews_order_fk
                FOREIGN KEY (order_id)
                REFERENCES {SCHEMA_NAME}.{ORDERS_TABLE}(order_id),

            CONSTRAINT reviews_score_chk
                CHECK (
                    review_score >= {MIN_REVIEW_SCORE}
                    AND
                    review_score <= {MAX_REVIEW_SCORE}
                ),

            CONSTRAINT reviews_chronology_chk
                CHECK (
                    review_creation_date
                    <=
                    review_answer_timestamp
                )
        )
    """

    with conn.cursor() as cur:
        cur.execute(create_sql)

    logger.info(
        "Target table validation/creation passed."
    )


def validate_target_is_empty(conn):

    with conn.cursor() as cur:

        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM {SCHEMA_NAME}.{TABLE_NAME}
            """
        )

        count = cur.fetchone()[0]

    if count != 0:
        raise ValueError(
            f"Target table {SCHEMA_NAME}.{TABLE_NAME} "
            f"is not empty. Existing records: {count}"
        )

    logger.info(
        "Target table is empty and ready for loading."
    )


# ---------------------------------------------------------------------------
# Foreign-key validation
# ---------------------------------------------------------------------------

def validate_orders_foreign_key(conn, df):

    logger.info(
        "Validating Reviews → Orders foreign-key relationship."
    )

    order_ids = set(
        df["order_id"].astype(str)
    )

    with conn.cursor() as cur:

        cur.execute(
            f"""
            SELECT order_id
            FROM {SCHEMA_NAME}.{ORDERS_TABLE}
            WHERE order_id = ANY(%s)
            """,
            (list(order_ids),),
        )

        existing_orders = {
            row[0]
            for row in cur.fetchall()
        }

    missing_orders = order_ids - existing_orders

    if missing_orders:

        sample = sorted(
            missing_orders
        )[:20]

        raise ValueError(
            "Reviews → Orders foreign-key validation failed. "
            f"Missing order IDs: {len(missing_orders)}. "
            f"Sample: {sample}"
        )

    logger.info(
        "Reviews → Orders foreign-key validation passed."
    )


# ---------------------------------------------------------------------------
# Bulk load
# ---------------------------------------------------------------------------

def bulk_load(conn, df):

    logger.info(
        "Starting bulk load into %s.%s.",
        SCHEMA_NAME,
        TABLE_NAME,
    )

    load_columns = [
        "review_id",
        "order_id",
        "review_score",
        "review_comment_title",
        "review_comment_message",
        "review_creation_date",
        "review_answer_timestamp",
    ]

    load_df = df[load_columns].copy()

    # Ensure timestamp columns are correctly represented.
    load_df["review_creation_date"] = pd.to_datetime(
        load_df["review_creation_date"]
    ).dt.strftime("%Y-%m-%d %H:%M:%S")

    load_df["review_answer_timestamp"] = pd.to_datetime(
        load_df["review_answer_timestamp"]
    ).dt.strftime("%Y-%m-%d %H:%M:%S")

    buffer = StringIO()

    load_df.to_csv(
        buffer,
        index=False,
        header=False,
        na_rep="\\N",
    )

    buffer.seek(0)

    with conn.cursor() as cur:

        copy_sql = f"""
            COPY {SCHEMA_NAME}.{TABLE_NAME}
            (
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

        cur.copy_expert(
            copy_sql,
            buffer,
        )

    logger.info(
        "Reviews bulk load completed successfully."
    )


# ---------------------------------------------------------------------------
# Post-load validation
# ---------------------------------------------------------------------------

def validate_row_count(conn, expected_count):

    with conn.cursor() as cur:

        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM {SCHEMA_NAME}.{TABLE_NAME}
            """
        )

        actual_count = cur.fetchone()[0]

    if actual_count != expected_count:
        raise ValueError(
            "Reviews row-count validation failed. "
            f"Expected {expected_count}, "
            f"found {actual_count}."
        )

    logger.info(
        "Reviews row-count validation passed: "
        "%s records.",
        actual_count,
    )


def validate_composite_key(conn):

    with conn.cursor() as cur:

        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT
                    review_id,
                    order_id
                FROM {SCHEMA_NAME}.{TABLE_NAME}
                GROUP BY
                    review_id,
                    order_id
                HAVING COUNT(*) > 1
            ) duplicates
            """
        )

        duplicate_groups = cur.fetchone()[0]

    if duplicate_groups > 0:
        raise ValueError(
            "Review composite-key validation failed: "
            f"{duplicate_groups} duplicate groups."
        )

    logger.info(
        "Review composite-key validation passed."
    )


def validate_required_fields(conn):

    with conn.cursor() as cur:

        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM {SCHEMA_NAME}.{TABLE_NAME}
            WHERE review_id IS NULL
               OR order_id IS NULL
               OR review_score IS NULL
               OR review_creation_date IS NULL
               OR review_answer_timestamp IS NULL
            """
        )

        invalid_count = cur.fetchone()[0]

    if invalid_count > 0:
        raise ValueError(
            "Reviews required-field validation failed: "
            f"{invalid_count} invalid records."
        )

    logger.info(
        "Reviews required-field validation passed."
    )


def validate_foreign_key_after_load(conn):

    logger.info(
        "Validating Reviews → Orders foreign-key "
        "relationship after load."
    )

    with conn.cursor() as cur:

        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM {SCHEMA_NAME}.{TABLE_NAME} r
            LEFT JOIN {SCHEMA_NAME}.{ORDERS_TABLE} o
                ON r.order_id = o.order_id
            WHERE o.order_id IS NULL
            """
        )

        orphan_count = cur.fetchone()[0]

    if orphan_count > 0:
        raise ValueError(
            "Reviews → Orders foreign-key validation "
            f"failed after load: {orphan_count} orphan records."
        )

    logger.info(
        "Reviews → Orders foreign-key validation passed."
    )


def validate_score_after_load(conn):

    with conn.cursor() as cur:

        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM {SCHEMA_NAME}.{TABLE_NAME}
            WHERE review_score < {MIN_REVIEW_SCORE}
               OR review_score > {MAX_REVIEW_SCORE}
            """
        )

        invalid_count = cur.fetchone()[0]

    if invalid_count > 0:
        raise ValueError(
            "Review score validation failed after load: "
            f"{invalid_count} invalid records."
        )

    logger.info(
        "Review score validation passed after load."
    )


def validate_chronology_after_load(conn):

    logger.info(
        "Validating review chronology after load."
    )

    with conn.cursor() as cur:

        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM {SCHEMA_NAME}.{TABLE_NAME}
            WHERE review_creation_date
                  >
                  review_answer_timestamp
            """
        )

        violation_count = cur.fetchone()[0]

    if violation_count > 0:
        raise ValueError(
            "Review chronology validation failed after load: "
            f"{violation_count} records."
        )

    logger.info(
        "Review chronology validation passed after load."
    )


def validate_timestamp_ranges(conn):

    with conn.cursor() as cur:

        cur.execute(
            f"""
            SELECT
                MIN(review_creation_date),
                MAX(review_creation_date),
                MIN(review_answer_timestamp),
                MAX(review_answer_timestamp)
            FROM {SCHEMA_NAME}.{TABLE_NAME}
            """
        )

        (
            creation_min,
            creation_max,
            answer_min,
            answer_max,
        ) = cur.fetchone()

    logger.info(
        "Target review creation range: %s to %s",
        creation_min,
        creation_max,
    )

    logger.info(
        "Target review answer range: %s to %s",
        answer_min,
        answer_max,
    )


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------

def create_indexes(conn):

    logger.info(
        "Creating review indexes."
    )

    index_statements = [

        f"""
        CREATE INDEX IF NOT EXISTS
        idx_reviews_order_id
        ON {SCHEMA_NAME}.{TABLE_NAME}(order_id)
        """,

        f"""
        CREATE INDEX IF NOT EXISTS
        idx_reviews_score
        ON {SCHEMA_NAME}.{TABLE_NAME}(review_score)
        """,

        f"""
        CREATE INDEX IF NOT EXISTS
        idx_reviews_creation_date
        ON {SCHEMA_NAME}.{TABLE_NAME}(review_creation_date)
        """,

        f"""
        CREATE INDEX IF NOT EXISTS
        idx_reviews_answer_timestamp
        ON {SCHEMA_NAME}.{TABLE_NAME}(review_answer_timestamp)
        """,
    ]

    with conn.cursor() as cur:

        for statement in index_statements:
            cur.execute(statement)

    logger.info(
        "Review indexes created successfully."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    conn = None

    try:

        logger.info("=" * 60)
        logger.info(
            "Starting Olist reviews data load."
        )
        logger.info("=" * 60)

        # --------------------------------------------------------------
        # Source validation
        # --------------------------------------------------------------

        df = validate_source_file()

        source_count = len(df)

        # --------------------------------------------------------------
        # Database
        # --------------------------------------------------------------

        conn = get_connection()

        ensure_schema(conn)

        ensure_target_table(conn)

        validate_target_is_empty(conn)

        # --------------------------------------------------------------
        # Foreign-key validation before loading
        # --------------------------------------------------------------

        validate_orders_foreign_key(
            conn,
            df,
        )

        # --------------------------------------------------------------
        # Bulk load
        # --------------------------------------------------------------

        bulk_load(
            conn,
            df,
        )

        # --------------------------------------------------------------
        # Post-load validation
        # --------------------------------------------------------------

        validate_row_count(
            conn,
            source_count,
        )

        validate_composite_key(conn)

        validate_required_fields(conn)

        validate_foreign_key_after_load(conn)

        validate_score_after_load(conn)

        validate_chronology_after_load(conn)

        validate_timestamp_ranges(conn)

        # --------------------------------------------------------------
        # Indexes
        # --------------------------------------------------------------

        create_indexes(conn)

        # --------------------------------------------------------------
        # Commit
        # --------------------------------------------------------------

        conn.commit()

        logger.info(
            "Reviews transaction committed successfully."
        )

        logger.info("=" * 60)
        logger.info(
            "Reviews load completed successfully."
        )
        logger.info(
            "Source records: %s",
            source_count,
        )
        logger.info(
            "Target table: %s.%s",
            SCHEMA_NAME,
            TABLE_NAME,
        )
        logger.info(
            "Target records: %s",
            source_count,
        )
        logger.info("=" * 60)

    except Exception as exc:

        if conn is not None:
            conn.rollback()

        logger.error(
            "Reviews load FAILED: %s",
            exc,
        )

        sys.exit(1)

    finally:

        if conn is not None:
            conn.close()

            logger.info(
                "PostgreSQL connection closed."
            )


if __name__ == "__main__":
    main()