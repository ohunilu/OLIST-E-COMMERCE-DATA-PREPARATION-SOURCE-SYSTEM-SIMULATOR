"""
Load transformed Olist payment data into PostgreSQL.

Source:
    /app/simulated_data/payments.csv

Target:
    public.payments

Known source-data anomaly:
    Two credit-card payment records contain payment_installments = 0.
    These records are preserved intentionally and validated after loading.
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

SOURCE_FILE = "/app/simulated_data/payments.csv"

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce_source")
DB_USER = os.getenv("POSTGRES_USER", "olist_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "olist_password")

SCHEMA_NAME = "public"
TABLE_NAME = "payments"
ORDERS_TABLE = "orders"

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


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database helpers
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

    logger.info("PostgreSQL connection established successfully.")

    return conn


def ensure_schema(conn):
    """Ensure target PostgreSQL schema exists."""

    logger.info("Ensuring PostgreSQL schema exists: %s", SCHEMA_NAME)

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(SCHEMA_NAME)
            )
        )

    conn.commit()


# ---------------------------------------------------------------------------
# Source validation
# ---------------------------------------------------------------------------

def validate_source_file():
    """Read and validate transformed payments source file."""

    logger.info("Reading payments source file: %s", SOURCE_FILE)

    if not os.path.exists(SOURCE_FILE):
        raise FileNotFoundError(
            f"Payments source file not found: {SOURCE_FILE}"
        )

    logger.info("Payments source file validation passed.")

    df = pd.read_csv(SOURCE_FILE)

    # ------------------------------------------------------------------
    # Schema validation
    # ------------------------------------------------------------------

    logger.info("Payments source schema validation passed.")

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
            "Payments source schema mismatch. "
            f"Missing columns: {missing_columns}; "
            f"Unexpected columns: {unexpected_columns}"
        )

    logger.info("Source records available for loading: %s", len(df))

    # ------------------------------------------------------------------
    # Required-field validation
    # ------------------------------------------------------------------

    required_columns = [
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
    ]

    null_counts = df[required_columns].isna().sum()

    invalid_nulls = null_counts[null_counts > 0]

    if not invalid_nulls.empty:
        raise ValueError(
            "Payments required-field validation failed: "
            f"{invalid_nulls.to_dict()}"
        )

    logger.info("Payments required-field validation passed.")

    # ------------------------------------------------------------------
    # Composite-key validation
    # ------------------------------------------------------------------

    duplicate_count = df.duplicated(
        ["order_id", "payment_sequential"]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            "Payment composite-key validation failed: "
            f"{duplicate_count} duplicate order_id + "
            "payment_sequential records."
        )

    logger.info("Payment composite-key validation passed.")

    # ------------------------------------------------------------------
    # Sequential validation
    # ------------------------------------------------------------------

    if (df["payment_sequential"] < 1).any():
        invalid_count = (
            df["payment_sequential"] < 1
        ).sum()

        raise ValueError(
            "Payment sequential validation failed: "
            f"{invalid_count} invalid values."
        )

    logger.info("Payment sequential validation passed.")

    # ------------------------------------------------------------------
    # Payment type validation
    # ------------------------------------------------------------------

    actual_payment_types = set(
        df["payment_type"].dropna().unique()
    )

    unexpected_payment_types = (
        actual_payment_types - PAYMENT_TYPES
    )

    if unexpected_payment_types:
        raise ValueError(
            "Payment type validation failed. "
            f"Unexpected payment types: "
            f"{sorted(unexpected_payment_types)}"
        )

    logger.info("Payment type validation passed.")

    logger.info(
        "Payment type distribution: %s",
        df["payment_type"].value_counts().to_dict(),
    )

    # ------------------------------------------------------------------
    # Payment installments validation
    # ------------------------------------------------------------------

    zero_installments = df[
        df["payment_installments"] == 0
    ]

    invalid_negative = df[
        df["payment_installments"] < 0
    ]

    above_max = df[
        df["payment_installments"] > MAX_INSTALLMENTS
    ]

    if len(invalid_negative) > 0:
        raise ValueError(
            "Payments installment validation failed: "
            f"{len(invalid_negative)} negative values."
        )

    if len(above_max) > 0:
        raise ValueError(
            "Payments installment validation failed: "
            f"{len(above_max)} values greater than "
            f"{MAX_INSTALLMENTS}."
        )

    # --------------------------------------------------------------
    # Known source anomaly handling
    # --------------------------------------------------------------

    if len(zero_installments) > 0:

        logger.warning(
            "Known source payment anomaly: "
            "payment_installments = 0 found in %s records.",
            len(zero_installments),
        )

        logger.warning(
            "Known zero-installment payment records:\n%s",
            zero_installments[
                [
                    "order_id",
                    "payment_sequential",
                    "payment_type",
                    "payment_installments",
                    "payment_value",
                ]
            ].to_string(index=False),
        )

        if len(zero_installments) != KNOWN_ZERO_INSTALLMENT_COUNT:
            raise ValueError(
                "Unexpected number of known zero-installment "
                "payment anomalies. "
                f"Expected {KNOWN_ZERO_INSTALLMENT_COUNT}, "
                f"found {len(zero_installments)}."
            )

        non_credit_card_zero = zero_installments[
            zero_installments["payment_type"] != "credit_card"
        ]

        if len(non_credit_card_zero) > 0:
            raise ValueError(
                "Unexpected zero-installment payment anomaly: "
                "non-credit-card payment contains "
                "payment_installments = 0."
            )

        logger.warning(
            "Payment installment anomalies are preserved."
        )

    logger.info(
        "Payment installments validation passed with "
        "%s known source-data anomaly records.",
        len(zero_installments),
    )

    # ------------------------------------------------------------------
    # Payment value validation
    # ------------------------------------------------------------------

    if (df["payment_value"] < 0).any():
        invalid_count = (
            df["payment_value"] < 0
        ).sum()

        raise ValueError(
            "Payment value validation failed: "
            f"{invalid_count} negative values."
        )

    logger.info("Payment value validation passed.")

    return df


# ---------------------------------------------------------------------------
# Target table creation
# ---------------------------------------------------------------------------

def ensure_target_table(conn):
    """Create and validate public.payments."""

    logger.info(
        "Ensuring target table exists: %s.%s",
        SCHEMA_NAME,
        TABLE_NAME,
    )

    create_sql = f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA_NAME}.{TABLE_NAME} (
            order_id TEXT NOT NULL,
            payment_sequential INTEGER NOT NULL,
            payment_type TEXT NOT NULL,
            payment_installments INTEGER NOT NULL,
            payment_value NUMERIC(12, 2) NOT NULL,

            CONSTRAINT payments_pkey
                PRIMARY KEY (order_id, payment_sequential),

            CONSTRAINT payments_order_fk
                FOREIGN KEY (order_id)
                REFERENCES {SCHEMA_NAME}.{ORDERS_TABLE}(order_id),

            CONSTRAINT payments_installments_max_chk
                CHECK (payment_installments <= {MAX_INSTALLMENTS}),

            CONSTRAINT payments_value_nonnegative_chk
                CHECK (payment_value >= 0)
        )
    """

    with conn.cursor() as cur:
        cur.execute(create_sql)

    logger.info("Target table validation/creation passed.")


# ---------------------------------------------------------------------------
# Target validation
# ---------------------------------------------------------------------------

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

    logger.info("Target table is empty and ready for loading.")


def validate_orders_foreign_key(conn, df):

    logger.info(
        "Validating Payments → Orders foreign-key relationship."
    )

    order_ids = set(df["order_id"].astype(str))

    if not order_ids:
        raise ValueError(
            "No order IDs found in payment source."
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
        sample = sorted(missing_orders)[:20]

        raise ValueError(
            "Payments → Orders foreign-key validation failed. "
            f"Missing order IDs: {len(missing_orders)}. "
            f"Sample: {sample}"
        )

    logger.info(
        "Payments → Orders foreign-key validation passed."
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
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
    ]

    buffer = StringIO()

    df[load_columns].to_csv(
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
                order_id,
                payment_sequential,
                payment_type,
                payment_installments,
                payment_value
            )
            FROM STDIN
            WITH CSV
        """

        cur.copy_expert(copy_sql, buffer)

    logger.info(
        "Payments bulk load completed successfully."
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
            "Payments row-count validation failed. "
            f"Expected {expected_count}, "
            f"found {actual_count}."
        )

    logger.info(
        "Payments row-count validation passed: %s records.",
        actual_count,
    )


def validate_primary_key(conn):

    with conn.cursor() as cur:

        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT order_id, payment_sequential
                FROM {SCHEMA_NAME}.{TABLE_NAME}
                GROUP BY order_id, payment_sequential
                HAVING COUNT(*) > 1
            ) duplicates
            """
        )

        duplicate_groups = cur.fetchone()[0]

    if duplicate_groups > 0:
        raise ValueError(
            "Payment primary-key validation failed: "
            f"{duplicate_groups} duplicate composite keys."
        )

    logger.info(
        "Payment composite-key validation passed."
    )


def validate_required_fields(conn):

    with conn.cursor() as cur:

        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM {SCHEMA_NAME}.{TABLE_NAME}
            WHERE order_id IS NULL
               OR payment_sequential IS NULL
               OR payment_type IS NULL
               OR payment_installments IS NULL
               OR payment_value IS NULL
            """
        )

        invalid_count = cur.fetchone()[0]

    if invalid_count > 0:
        raise ValueError(
            "Payments required-field validation failed: "
            f"{invalid_count} records contain NULL required fields."
        )

    logger.info(
        "Payments required-field validation passed."
    )


def validate_foreign_key_after_load(conn):

    logger.info(
        "Validating Payments → Orders foreign-key relationship "
        "after load."
    )

    with conn.cursor() as cur:

        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM {SCHEMA_NAME}.{TABLE_NAME} p
            LEFT JOIN {SCHEMA_NAME}.{ORDERS_TABLE} o
                ON p.order_id = o.order_id
            WHERE o.order_id IS NULL
            """
        )

        missing_count = cur.fetchone()[0]

    if missing_count > 0:
        raise ValueError(
            "Payments → Orders foreign-key validation failed "
            f"after load: {missing_count} orphan records."
        )

    logger.info(
        "Payments → Orders foreign-key validation passed."
    )


def validate_installment_anomalies_after_load(conn):

    with conn.cursor() as cur:

        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM {SCHEMA_NAME}.{TABLE_NAME}
            WHERE payment_installments = 0
            """
        )

        zero_count = cur.fetchone()[0]

        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM {SCHEMA_NAME}.{TABLE_NAME}
            WHERE payment_installments < 0
               OR payment_installments > {MAX_INSTALLMENTS}
            """
        )

        invalid_count = cur.fetchone()[0]

    if zero_count != KNOWN_ZERO_INSTALLMENT_COUNT:
        raise ValueError(
            "Payment installment anomaly preservation validation "
            "failed. "
            f"Expected {KNOWN_ZERO_INSTALLMENT_COUNT} zero-installment "
            f"records, found {zero_count}."
        )

    if invalid_count != 0:
        raise ValueError(
            "Payment installment range validation failed after load: "
            f"{invalid_count} records outside allowed maximum range."
        )

    logger.warning(
        "Target payment installment validation contains "
        "%s known source-data anomaly records.",
        zero_count,
    )

    logger.info(
        "Payment installment anomaly preservation validation passed."
    )


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------

def create_indexes(conn):

    logger.info("Creating payment indexes.")

    index_statements = [
        f"""
        CREATE INDEX IF NOT EXISTS idx_payments_order_id
        ON {SCHEMA_NAME}.{TABLE_NAME}(order_id)
        """,
        f"""
        CREATE INDEX IF NOT EXISTS idx_payments_type
        ON {SCHEMA_NAME}.{TABLE_NAME}(payment_type)
        """,
        f"""
        CREATE INDEX IF NOT EXISTS idx_payments_sequential
        ON {SCHEMA_NAME}.{TABLE_NAME}(payment_sequential)
        """,
    ]

    with conn.cursor() as cur:

        for statement in index_statements:
            cur.execute(statement)

    logger.info("Payment indexes created successfully.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    conn = None

    try:

        logger.info("=" * 60)
        logger.info("Starting Olist payments data load.")
        logger.info("=" * 60)

        # --------------------------------------------------------------
        # Source validation
        # --------------------------------------------------------------

        df = validate_source_file()

        source_count = len(df)

        # --------------------------------------------------------------
        # Database connection
        # --------------------------------------------------------------

        conn = get_connection()

        ensure_schema(conn)

        ensure_target_table(conn)

        validate_target_is_empty(conn)

        # --------------------------------------------------------------
        # Cross-table validation
        # --------------------------------------------------------------

        validate_orders_foreign_key(conn, df)

        # --------------------------------------------------------------
        # Bulk load
        # --------------------------------------------------------------

        bulk_load(conn, df)

        # --------------------------------------------------------------
        # Post-load validation
        # --------------------------------------------------------------

        validate_row_count(
            conn,
            source_count,
        )

        validate_primary_key(conn)

        validate_required_fields(conn)

        validate_foreign_key_after_load(conn)

        validate_installment_anomalies_after_load(conn)

        # --------------------------------------------------------------
        # Indexes
        # --------------------------------------------------------------

        create_indexes(conn)

        # --------------------------------------------------------------
        # Commit
        # --------------------------------------------------------------

        conn.commit()

        logger.info(
            "Payments transaction committed successfully."
        )

        logger.info("=" * 60)
        logger.info(
            "Payments load completed successfully."
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
        logger.info(
            "Known zero-installment anomalies preserved: %s",
            KNOWN_ZERO_INSTALLMENT_COUNT,
        )
        logger.info("=" * 60)

    except Exception as exc:

        if conn is not None:
            conn.rollback()

        logger.error(
            "Payments load FAILED: %s",
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