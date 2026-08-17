import logging
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values


# ============================================================
# Configuration
# ============================================================

SOURCE_FILE = Path("/app/simulated_data/orders.csv")

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce_source")
DB_USER = os.getenv("POSTGRES_USER", "olist_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")

SCHEMA_NAME = "public"
TABLE_NAME = "orders"
CUSTOMERS_TABLE = "customers"

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


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# Helpers
# ============================================================

def fail(message: str):
    logger.error(message)
    raise RuntimeError(message)


def validate_source_file() -> pd.DataFrame:
    logger.info("Reading orders source file: %s", SOURCE_FILE)

    if not SOURCE_FILE.exists():
        fail(f"Orders source file does not exist: {SOURCE_FILE}")

    df = pd.read_csv(SOURCE_FILE)

    if df.empty:
        fail("Orders source file is empty.")

    logger.info("Orders source file validation passed.")

    actual_columns = df.columns.tolist()

    if actual_columns != EXPECTED_COLUMNS:
        fail(
            "Orders source schema mismatch.\n"
            f"Expected: {EXPECTED_COLUMNS}\n"
            f"Actual:   {actual_columns}"
        )

    logger.info("Orders source schema validation passed.")

    logger.info("Source records available for loading: %s", len(df))

    return df


def validate_source_data(df: pd.DataFrame):
    # --------------------------------------------------------
    # Primary key validation
    # --------------------------------------------------------

    if df["order_id"].isna().any():
        fail("Orders contain NULL order_id values.")

    duplicate_order_ids = df["order_id"].duplicated().sum()

    if duplicate_order_ids > 0:
        fail(
            f"Orders contain {duplicate_order_ids} duplicate order_id values."
        )

    logger.info("Order primary-key validation passed.")

    # --------------------------------------------------------
    # Required fields
    # --------------------------------------------------------

    required_columns = [
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
    ]

    null_counts = df[required_columns].isna().sum()

    if null_counts.any():
        fail(
            "Orders contain NULL values in required fields:\n"
            f"{null_counts[null_counts > 0]}"
        )

    logger.info("Orders required-field validation passed.")

    # --------------------------------------------------------
    # Timestamp parsing
    # --------------------------------------------------------

    timestamp_columns = [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]

    for column in timestamp_columns:
        parsed = pd.to_datetime(df[column], errors="coerce")

        invalid_mask = df[column].notna() & parsed.isna()

        if invalid_mask.any():
            fail(
                f"Orders contain invalid timestamps in {column}: "
                f"{invalid_mask.sum()} records."
            )

        df[column] = parsed

    logger.info("Order timestamp parsing validation passed.")

    # --------------------------------------------------------
    # Purchase timestamp validation
    # --------------------------------------------------------

    if df["order_purchase_timestamp"].isna().any():
        fail("Orders contain NULL order_purchase_timestamp values.")

    purchase_min = df["order_purchase_timestamp"].min()
    purchase_max = df["order_purchase_timestamp"].max()

    logger.info(
        "Order purchase timestamp range: %s to %s",
        purchase_min,
        purchase_max,
    )

    # --------------------------------------------------------
    # Order chronology validation
    # --------------------------------------------------------

    chronology_checks = [
        (
            "order_purchase_timestamp",
            "order_approved_at",
            "purchase <= approved",
        ),
        (
            "order_approved_at",
            "order_delivered_carrier_date",
            "approved <= carrier",
        ),
        (
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "carrier <= customer delivery",
        ),
    ]

    total_chronology_violations = 0

    for earlier, later, description in chronology_checks:

        mask = (
            df[earlier].notna()
            & df[later].notna()
            & (df[earlier] > df[later])
        )

        violations = int(mask.sum())

        if violations > 0:
            total_chronology_violations += violations

            logger.warning(
                "Known source chronology anomaly: %s violated in %s records.",
                description,
                f"{violations:,}",
            )
        else:
            logger.info(
                "Order chronology check passed: %s.",
                description,
            )

    logger.warning(
        "Order chronology validation completed with %s known "
        "source-data anomaly records. Anomalies are preserved.",
        f"{total_chronology_violations:,}",
    )
    # --------------------------------------------------------
    # Estimated delivery validation
    # --------------------------------------------------------

    invalid_estimates = (
        df["order_estimated_delivery_date"].notna()
        & (
            df["order_estimated_delivery_date"]
            < df["order_purchase_timestamp"]
        )
    )

    if invalid_estimates.any():
        fail(
            "Estimated delivery date occurs before purchase timestamp "
            f"in {invalid_estimates.sum()} records."
        )

    logger.info("Order estimated-delivery validation passed.")


# ============================================================
# Database
# ============================================================

def get_connection():
    logger.info(
        "Connecting to PostgreSQL: host=%s port=%s database=%s user=%s",
        DB_HOST,
        DB_PORT,
        DB_NAME,
        DB_USER,
    )

    if not DB_PASSWORD:
        fail(
            "POSTGRES_PASSWORD is not set. "
            "Set it in the preparation container environment."
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


def ensure_schema_and_table(conn):
    logger.info(
        "Ensuring PostgreSQL schema exists: %s",
        SCHEMA_NAME,
    )

    with conn.cursor() as cur:

        cur.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(SCHEMA_NAME)
            )
        )

        logger.info(
            "Ensuring target table exists: %s.%s",
            SCHEMA_NAME,
            TABLE_NAME,
        )

        cur.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {}.{} (
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
                        REFERENCES {}.{} (customer_id)
                )
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(CUSTOMERS_TABLE),
            )
        )

    logger.info("Target table validation/creation passed.")


def ensure_target_table_empty(conn):
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                "SELECT COUNT(*) FROM {}.{}"
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

        count = cur.fetchone()[0]

    if count > 0:
        fail(
            f"Target table {SCHEMA_NAME}.{TABLE_NAME} already contains "
            f"{count:,} records. Loader will not overwrite a populated table."
        )

    logger.info("Target table is empty and ready for loading.")


# ============================================================
# Customer foreign-key validation
# ============================================================

def validate_customer_references(conn, df: pd.DataFrame):

    logger.info(
        "Validating Orders → Customers foreign-key relationship."
    )

    source_customer_ids = set(df["customer_id"].astype(str))

    with conn.cursor() as cur:

        cur.execute(
            sql.SQL(
                """
                SELECT customer_id
                FROM {}.{}
                WHERE customer_id = ANY(%s)
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(CUSTOMERS_TABLE),
            ),
            (list(source_customer_ids),),
        )

        existing_customer_ids = {
            row[0] for row in cur.fetchall()
        }

    missing_customer_ids = (
        source_customer_ids - existing_customer_ids
    )

    if missing_customer_ids:
        sample = sorted(missing_customer_ids)[:20]

        fail(
            "Orders contain customer_id values that do not exist "
            f"in {SCHEMA_NAME}.{CUSTOMERS_TABLE}.\n"
            f"Missing customer IDs: {len(missing_customer_ids):,}\n"
            f"Sample: {sample}"
        )

    logger.info(
        "Orders → Customers foreign-key validation passed."
    )


# ============================================================
# Bulk load
# ============================================================

def bulk_load_orders(conn, df: pd.DataFrame):

    logger.info(
        "Starting bulk load into %s.%s.",
        SCHEMA_NAME,
        TABLE_NAME,
    )

    columns = EXPECTED_COLUMNS

    records = []

    for row in df.itertuples(index=False, name=None):

        cleaned = []

        for value in row:
            if pd.isna(value):
                cleaned.append(None)
            elif isinstance(value, pd.Timestamp):
                cleaned.append(value.to_pydatetime())
            else:
                cleaned.append(value)

        records.append(tuple(cleaned))

    insert_query = sql.SQL(
        """
        INSERT INTO {}.{} (
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
        sql.Identifier(SCHEMA_NAME),
        sql.Identifier(TABLE_NAME),
    )

    with conn.cursor() as cur:

        execute_values(
            cur,
            insert_query.as_string(conn),
            records,
            page_size=5000,
        )

    logger.info("Orders bulk load completed successfully.")


# ============================================================
# Target validation
# ============================================================

def validate_target(conn, source_df: pd.DataFrame):

    with conn.cursor() as cur:

        # ----------------------------------------------------
        # Row count
        # ----------------------------------------------------

        cur.execute(
            sql.SQL(
                "SELECT COUNT(*) FROM {}.{}"
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

        target_count = cur.fetchone()[0]
        source_count = len(source_df)

        if target_count != source_count:
            fail(
                "Orders row-count validation failed: "
                f"source={source_count:,}, target={target_count:,}"
            )

        logger.info(
            "Orders row-count validation passed: %s records.",
            target_count,
        )

        # ----------------------------------------------------
        # Primary key
        # ----------------------------------------------------

        cur.execute(
            sql.SQL(
                """
                SELECT COUNT(*), COUNT(DISTINCT order_id)
                FROM {}.{}
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

        total, unique_ids = cur.fetchone()

        if total != unique_ids:
            fail(
                "Order primary-key validation failed: "
                f"total={total:,}, unique={unique_ids:,}"
            )

        logger.info("Order primary-key validation passed.")

        # ----------------------------------------------------
        # Required fields
        # ----------------------------------------------------

        cur.execute(
            sql.SQL(
                """
                SELECT
                    COUNT(*) FILTER (WHERE order_id IS NULL),
                    COUNT(*) FILTER (WHERE customer_id IS NULL),
                    COUNT(*) FILTER (WHERE order_status IS NULL),
                    COUNT(*) FILTER (
                        WHERE order_purchase_timestamp IS NULL
                    )
                FROM {}.{}
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

        null_counts = cur.fetchone()

        if any(null_counts):
            fail(
                "Orders required-field validation failed: "
                f"{null_counts}"
            )

        logger.info("Orders required-field validation passed.")

        # ----------------------------------------------------
        # Foreign key
        # ----------------------------------------------------

        cur.execute(
            sql.SQL(
                """
                SELECT COUNT(*)
                FROM {}.{} o
                LEFT JOIN {}.{} c
                    ON o.customer_id = c.customer_id
                WHERE c.customer_id IS NULL
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(CUSTOMERS_TABLE),
            )
        )

        orphan_count = cur.fetchone()[0]

        if orphan_count > 0:
            fail(
                "Orders → Customers foreign-key validation failed: "
                f"{orphan_count:,} orphan records."
            )

        logger.info(
            "Orders → Customers foreign-key validation passed."
        )

        # ----------------------------------------------------
        # Timestamp range
        # ----------------------------------------------------

        cur.execute(
            sql.SQL(
                """
                SELECT
                    MIN(order_purchase_timestamp),
                    MAX(order_purchase_timestamp)
                FROM {}.{}
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

        timestamp_min, timestamp_max = cur.fetchone()

        logger.info(
            "Order purchase timestamp range: %s to %s",
            timestamp_min,
            timestamp_max,
        )

        # ----------------------------------------------------
        # Target chronology
        # ----------------------------------------------------

        cur.execute(
            sql.SQL(
                """
                SELECT COUNT(*)
                FROM {}.{}
                WHERE
                    (
                        order_approved_at IS NOT NULL
                        AND order_purchase_timestamp > order_approved_at
                    )
                    OR
                    (
                        order_approved_at IS NOT NULL
                        AND order_delivered_carrier_date IS NOT NULL
                        AND order_approved_at > order_delivered_carrier_date
                    )
                    OR
                    (
                        order_delivered_carrier_date IS NOT NULL
                        AND order_delivered_customer_date IS NOT NULL
                        AND order_delivered_carrier_date
                            > order_delivered_customer_date
                    )
                    OR
                    (
                        order_estimated_delivery_date IS NOT NULL
                        AND order_estimated_delivery_date
                            < order_purchase_timestamp
                    )
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

        chronology_violations = cur.fetchone()[0]

        if chronology_violations > 0:
            logger.warning(
                "Target order chronology contains %s known source-data "
                "anomaly records. Anomalies were preserved during loading.",
                f"{chronology_violations:,}",
            )
        else:
            logger.info("Target order chronology validation passed.")


# ============================================================
# Indexes
# ============================================================

def create_indexes(conn):

    logger.info("Creating order indexes.")

    with conn.cursor() as cur:

        cur.execute(
            sql.SQL(
                """
                CREATE INDEX IF NOT EXISTS idx_orders_customer_id
                ON {}.{} (customer_id)
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

        cur.execute(
            sql.SQL(
                """
                CREATE INDEX IF NOT EXISTS idx_orders_purchase_timestamp
                ON {}.{} (order_purchase_timestamp)
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

        cur.execute(
            sql.SQL(
                """
                CREATE INDEX IF NOT EXISTS idx_orders_status
                ON {}.{} (order_status)
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )

    logger.info("Order indexes created successfully.")


# ============================================================
# Main
# ============================================================

def main():

    logger.info("=" * 60)
    logger.info("Starting Olist orders data load.")
    logger.info("=" * 60)

    conn = None

    try:

        # ----------------------------------------------------
        # Source validation
        # ----------------------------------------------------

        df = validate_source_file()

        validate_source_data(df)

        # ----------------------------------------------------
        # Database connection
        # ----------------------------------------------------

        conn = get_connection()

        ensure_schema_and_table(conn)

        ensure_target_table_empty(conn)

        # ----------------------------------------------------
        # Referential validation BEFORE loading
        # ----------------------------------------------------

        validate_customer_references(conn, df)

        # ----------------------------------------------------
        # Load
        # ----------------------------------------------------

        bulk_load_orders(conn, df)

        # ----------------------------------------------------
        # Target validation
        # ----------------------------------------------------

        validate_target(conn, df)

        # ----------------------------------------------------
        # Indexes
        # ----------------------------------------------------

        create_indexes(conn)

        # ----------------------------------------------------
        # Commit
        # ----------------------------------------------------

        conn.commit()

        logger.info("Orders transaction committed successfully.")

        # ----------------------------------------------------
        # Final summary
        # ----------------------------------------------------

        logger.info("=" * 60)
        logger.info("Orders load completed successfully.")
        logger.info("Source records: %s", f"{len(df):,}")
        logger.info(
            "Target table: %s.%s",
            SCHEMA_NAME,
            TABLE_NAME,
        )
        logger.info("Target records: %s", f"{len(df):,}")
        logger.info("=" * 60)

    except Exception as exc:

        if conn is not None:
            conn.rollback()
            logger.error(
                "Orders transaction rolled back because of an error."
            )

        logger.error("Orders load FAILED: %s", exc)

        sys.exit(1)

    finally:

        if conn is not None:
            conn.close()
            logger.info("PostgreSQL connection closed.")


if __name__ == "__main__":
    main()