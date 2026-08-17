"""
Load transformed Olist order_items data into PostgreSQL.

Source:
    /app/simulated_data/order_items.csv

Target:
    public.order_items

Relationships:
    order_id  -> public.orders.order_id
    product_id -> public.products.product_id
    seller_id  -> public.sellers.seller_id

The loader:
    1. Validates the source file and schema.
    2. Validates required fields and data types.
    3. Validates the order-item composite key.
    4. Validates numeric and non-negative monetary/quantity fields.
    5. Validates all foreign-key relationships before loading.
    6. Creates the target table if necessary.
    7. Performs a bulk PostgreSQL load.
    8. Re-validates the loaded data.
    9. Creates indexes.
    10. Commits only after all validations pass.
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

SOURCE_FILE = "/app/simulated_data/order_items.csv"

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "ecommerce_source")
DB_USER = os.getenv("POSTGRES_USER", "olist_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "olist_password")

SCHEMA_NAME = "public"
TABLE_NAME = "order_items"

EXPECTED_COLUMNS = [
    "order_id",
    "order_item_id",
    "product_id",
    "seller_id",
    "shipping_limit_date",
    "price",
    "freight_value",
]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_source_file():
    """Validate that the source file exists and is readable."""

    if not os.path.exists(SOURCE_FILE):
        raise FileNotFoundError(
            f"Order_items source file not found: {SOURCE_FILE}"
        )

    if not os.path.isfile(SOURCE_FILE):
        raise ValueError(
            f"Order_items source path is not a file: {SOURCE_FILE}"
        )

    logger.info("Order_items source file validation passed.")


def validate_schema(df):
    """Validate the source schema exactly."""

    actual_columns = list(df.columns)

    missing_columns = [
        column for column in EXPECTED_COLUMNS
        if column not in actual_columns
    ]

    unexpected_columns = [
        column for column in actual_columns
        if column not in EXPECTED_COLUMNS
    ]

    if missing_columns or unexpected_columns:
        raise ValueError(
            "Order_items source schema mismatch. "
            f"Missing columns: {missing_columns}; "
            f"Unexpected columns: {unexpected_columns}"
        )

    if actual_columns != EXPECTED_COLUMNS:
        raise ValueError(
            "Order_items source column order mismatch. "
            f"Expected: {EXPECTED_COLUMNS}; "
            f"Actual: {actual_columns}"
        )

    logger.info("Order_items source schema validation passed.")


def validate_required_fields(df):
    """Validate required fields are not null or blank."""

    required_columns = [
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
    ]

    for column in required_columns:
        null_count = df[column].isna().sum()

        if null_count > 0:
            raise ValueError(
                f"Order_items required-field validation failed: "
                f"{column} contains {null_count} null values."
            )

        if df[column].dtype == "object":
            blank_count = (
                df[column]
                .astype(str)
                .str.strip()
                .eq("")
                .sum()
            )

            if blank_count > 0:
                raise ValueError(
                    f"Order_items required-field validation failed: "
                    f"{column} contains {blank_count} blank values."
                )

    logger.info("Order_items required-field validation passed.")


def validate_primary_key(df):
    """
    Validate the order-item composite key.

    Olist order_items are uniquely identified by:
        order_id + order_item_id
    """

    duplicate_count = df.duplicated(
        subset=["order_id", "order_item_id"]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            "Order-item composite-key validation failed: "
            f"{duplicate_count} duplicate order_id + order_item_id "
            "combinations found."
        )

    logger.info("Order-item composite key validation passed.")


def validate_numeric_fields(df):
    """Validate numeric fields can be interpreted correctly."""

    numeric_columns = [
        "order_item_id",
        "price",
        "freight_value",
    ]

    for column in numeric_columns:
        converted = pd.to_numeric(
            df[column],
            errors="coerce",
        )

        invalid_count = converted.isna().sum()

        if invalid_count > 0:
            raise ValueError(
                f"Order_items numeric validation failed: "
                f"{column} contains {invalid_count} invalid numeric values."
            )

        df[column] = converted

    logger.info("Order_items numeric value validation passed.")


def validate_non_negative_values(df):
    """Validate price and freight values are non-negative."""

    for column in ["price", "freight_value"]:
        invalid_count = (df[column] < 0).sum()

        if invalid_count > 0:
            raise ValueError(
                f"Order_items non-negative validation failed: "
                f"{column} contains {invalid_count} negative values."
            )

    logger.info("Order_items non-negative value validation passed.")


def validate_item_sequence(df):
    """
    Validate order_item_id values.

    Each order's item sequence should begin at 1 and increase without gaps.
    """

    sequence_errors = []

    grouped = (
        df.groupby("order_id")["order_item_id"]
        .apply(lambda values: sorted(values.astype(int).tolist()))
    )

    for order_id, item_ids in grouped.items():
        expected = list(range(1, len(item_ids) + 1))

        if item_ids != expected:
            sequence_errors.append(
                (order_id, item_ids, expected)
            )

    if sequence_errors:
        logger.warning(
            "Order-item sequence validation identified "
            f"{len(sequence_errors)} orders with non-contiguous "
            "order_item_id values."
        )

        logger.warning(
            "The source sequence structure is preserved."
        )
    else:
        logger.info(
            "Order-item sequence validation passed."
        )


def validate_timestamp(df):
    """Validate shipping_limit_date can be parsed as a timestamp."""

    parsed = pd.to_datetime(
        df["shipping_limit_date"],
        errors="coerce",
    )

    invalid_count = parsed.isna().sum()

    if invalid_count > 0:
        raise ValueError(
            "Order_items timestamp validation failed: "
            f"{invalid_count} invalid shipping_limit_date values."
        )

    df["shipping_limit_date"] = parsed

    logger.info(
        "Order_items shipping timestamp validation passed."
    )


# ---------------------------------------------------------------------------
# PostgreSQL helpers
# ---------------------------------------------------------------------------

def connect_database():
    """Create PostgreSQL connection."""

    logger.info(
        "Connecting to PostgreSQL: "
        f"host={DB_HOST} port={DB_PORT} "
        f"database={DB_NAME} user={DB_USER}"
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
    """Ensure target schema exists."""

    logger.info(
        f"Ensuring PostgreSQL schema exists: {SCHEMA_NAME}"
    )

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(SCHEMA_NAME)
            )
        )


def ensure_target_table(conn):
    """Create order_items table if it does not already exist."""

    logger.info(
        f"Ensuring target table exists: "
        f"{SCHEMA_NAME}.{TABLE_NAME}"
    )

    create_sql = """
        CREATE TABLE IF NOT EXISTS public.order_items (
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
                REFERENCES public.orders(order_id),

            CONSTRAINT order_items_product_fk
                FOREIGN KEY (product_id)
                REFERENCES public.products(product_id),

            CONSTRAINT order_items_seller_fk
                FOREIGN KEY (seller_id)
                REFERENCES public.sellers(seller_id),

            CONSTRAINT order_items_price_nonnegative
                CHECK (price >= 0),

            CONSTRAINT order_items_freight_nonnegative
                CHECK (freight_value >= 0)
        )
    """

    with conn.cursor() as cur:
        cur.execute(create_sql)

    logger.info("Target table validation/creation passed.")


def validate_target_empty(conn):
    """Ensure target table is empty before loading."""

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM public.order_items"
        )

        count = cur.fetchone()[0]

    if count != 0:
        raise ValueError(
            "Target table public.order_items is not empty. "
            f"Existing records: {count}"
        )

    logger.info(
        "Target table is empty and ready for loading."
    )


# ---------------------------------------------------------------------------
# Foreign-key validation
# ---------------------------------------------------------------------------

def validate_foreign_keys(conn, df):
    """Validate order, product and seller references."""

    logger.info(
        "Validating Order_items → Orders foreign-key relationship."
    )

    with conn.cursor() as cur:

        cur.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT order_id
                FROM (
                    SELECT UNNEST(%s::text[]) AS order_id
                ) source_ids
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM public.orders o
                    WHERE o.order_id = source_ids.order_id
                )
            ) missing
            """,
            (df["order_id"].astype(str).tolist(),),
        )

        missing_orders = cur.fetchone()[0]

    if missing_orders > 0:
        raise ValueError(
            "Order_items → Orders foreign-key validation failed: "
            f"{missing_orders} order references are missing."
        )

    logger.info(
        "Order_items → Orders foreign-key validation passed."
    )

    logger.info(
        "Validating Order_items → Products foreign-key relationship."
    )

    with conn.cursor() as cur:

        cur.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT product_id
                FROM (
                    SELECT UNNEST(%s::text[]) AS product_id
                ) source_ids
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM public.products p
                    WHERE p.product_id = source_ids.product_id
                )
            ) missing
            """,
            (df["product_id"].astype(str).tolist(),),
        )

        missing_products = cur.fetchone()[0]

    if missing_products > 0:
        raise ValueError(
            "Order_items → Products foreign-key validation failed: "
            f"{missing_products} product references are missing."
        )

    logger.info(
        "Order_items → Products foreign-key validation passed."
    )

    logger.info(
        "Validating Order_items → Sellers foreign-key relationship."
    )

    with conn.cursor() as cur:

        cur.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT seller_id
                FROM (
                    SELECT UNNEST(%s::text[]) AS seller_id
                ) source_ids
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM public.sellers s
                    WHERE s.seller_id = source_ids.seller_id
                )
            ) missing
            """,
            (df["seller_id"].astype(str).tolist(),),
        )

        missing_sellers = cur.fetchone()[0]

    if missing_sellers > 0:
        raise ValueError(
            "Order_items → Sellers foreign-key validation failed: "
            f"{missing_sellers} seller references are missing."
        )

    logger.info(
        "Order_items → Sellers foreign-key validation passed."
    )


# ---------------------------------------------------------------------------
# Bulk loading
# ---------------------------------------------------------------------------

def bulk_load(conn, df):
    """Bulk load dataframe into PostgreSQL using COPY."""

    logger.info(
        f"Starting bulk load into "
        f"{SCHEMA_NAME}.{TABLE_NAME}."
    )

    load_df = df.copy()

    load_df["shipping_limit_date"] = (
        load_df["shipping_limit_date"]
        .dt.strftime("%Y-%m-%d %H:%M:%S")
    )

    buffer = StringIO()

    load_df.to_csv(
        buffer,
        index=False,
        header=False,
        na_rep="\\N",
    )

    buffer.seek(0)

    copy_sql = """
        COPY public.order_items (
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

    with conn.cursor() as cur:
        cur.copy_expert(copy_sql, buffer)

    logger.info(
        "Order_items bulk load completed successfully."
    )


# ---------------------------------------------------------------------------
# Post-load validation
# ---------------------------------------------------------------------------

def validate_loaded_data(conn, expected_count):
    """Perform post-load integrity checks."""

    with conn.cursor() as cur:

        cur.execute(
            "SELECT COUNT(*) FROM public.order_items"
        )

        actual_count = cur.fetchone()[0]

    if actual_count != expected_count:
        raise ValueError(
            "Order_items row-count validation failed: "
            f"expected {expected_count}, found {actual_count}."
        )

    logger.info(
        f"Order_items row-count validation passed: "
        f"{actual_count:,} records."
    )

    # Primary key validation
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT order_id, order_item_id
                FROM public.order_items
                GROUP BY order_id, order_item_id
                HAVING COUNT(*) > 1
            ) duplicates
            """
        )

        duplicate_count = cur.fetchone()[0]

    if duplicate_count > 0:
        raise ValueError(
            "Order-item composite-key validation failed after load: "
            f"{duplicate_count} duplicate keys found."
        )

    logger.info(
        "Order-item composite-key validation passed."
    )

    # Required fields
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE order_id IS NULL),
                COUNT(*) FILTER (WHERE order_item_id IS NULL),
                COUNT(*) FILTER (WHERE product_id IS NULL),
                COUNT(*) FILTER (WHERE seller_id IS NULL),
                COUNT(*) FILTER (WHERE shipping_limit_date IS NULL),
                COUNT(*) FILTER (WHERE price IS NULL),
                COUNT(*) FILTER (WHERE freight_value IS NULL)
            FROM public.order_items
            """
        )

        null_counts = cur.fetchone()

    if any(null_counts):
        raise ValueError(
            "Order_items required-field validation failed after load: "
            f"null counts = {null_counts}"
        )

    logger.info(
        "Order_items required-field validation passed."
    )

    # Foreign keys
    with conn.cursor() as cur:

        cur.execute(
            """
            SELECT COUNT(*)
            FROM public.order_items oi
            LEFT JOIN public.orders o
                ON oi.order_id = o.order_id
            WHERE o.order_id IS NULL
            """
        )

        missing_orders = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*)
            FROM public.order_items oi
            LEFT JOIN public.products p
                ON oi.product_id = p.product_id
            WHERE p.product_id IS NULL
            """
        )

        missing_products = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*)
            FROM public.order_items oi
            LEFT JOIN public.sellers s
                ON oi.seller_id = s.seller_id
            WHERE s.seller_id IS NULL
            """
        )

        missing_sellers = cur.fetchone()[0]

    if missing_orders > 0:
        raise ValueError(
            "Order_items → Orders foreign-key validation failed "
            f"after load: {missing_orders} missing references."
        )

    if missing_products > 0:
        raise ValueError(
            "Order_items → Products foreign-key validation failed "
            f"after load: {missing_products} missing references."
        )

    if missing_sellers > 0:
        raise ValueError(
            "Order_items → Sellers foreign-key validation failed "
            f"after load: {missing_sellers} missing references."
        )

    logger.info(
        "Order_items foreign-key validation passed after load."
    )


def create_indexes(conn):
    """Create indexes supporting downstream joins and analysis."""

    logger.info("Creating order-item indexes.")

    index_statements = [
        """
        CREATE INDEX IF NOT EXISTS idx_order_items_product_id
        ON public.order_items(product_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_order_items_seller_id
        ON public.order_items(seller_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_order_items_shipping_limit_date
        ON public.order_items(shipping_limit_date)
        """,
    ]

    with conn.cursor() as cur:
        for statement in index_statements:
            cur.execute(statement)

    logger.info(
        "Order-item indexes created successfully."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    logger.info("=" * 60)
    logger.info("Starting Olist order_items data load.")
    logger.info("=" * 60)

    conn = None

    try:

        # ---------------------------------------------------------------
        # Source validation
        # ---------------------------------------------------------------

        validate_source_file()

        logger.info(
            f"Reading order_items source file: {SOURCE_FILE}"
        )

        df = pd.read_csv(SOURCE_FILE)

        logger.info(
            f"Order_items source records loaded: {len(df):,}"
        )

        validate_schema(df)

        logger.info(
            f"Source records available for loading: {len(df):,}"
        )

        validate_required_fields(df)
        validate_primary_key(df)
        validate_numeric_fields(df)
        validate_non_negative_values(df)
        validate_timestamp(df)
        validate_item_sequence(df)

        # ---------------------------------------------------------------
        # Database connection
        # ---------------------------------------------------------------

        conn = connect_database()

        ensure_schema(conn)
        ensure_target_table(conn)
        validate_target_empty(conn)

        # ---------------------------------------------------------------
        # Foreign-key validation
        # ---------------------------------------------------------------

        validate_foreign_keys(conn, df)

        # ---------------------------------------------------------------
        # Bulk load
        # ---------------------------------------------------------------

        bulk_load(conn, df)

        # ---------------------------------------------------------------
        # Post-load validation
        # ---------------------------------------------------------------

        validate_loaded_data(
            conn,
            expected_count=len(df),
        )

        # ---------------------------------------------------------------
        # Indexes
        # ---------------------------------------------------------------

        create_indexes(conn)

        # ---------------------------------------------------------------
        # Commit
        # ---------------------------------------------------------------

        conn.commit()

        logger.info(
            "Order_items transaction committed successfully."
        )

        logger.info("=" * 60)
        logger.info("Order_items load completed successfully.")
        logger.info(f"Source records: {len(df):,}")
        logger.info(
            f"Target table: {SCHEMA_NAME}.{TABLE_NAME}"
        )
        logger.info(
            f"Target records: {len(df):,}"
        )
        logger.info("=" * 60)

    except Exception as exc:

        if conn is not None:
            conn.rollback()

        logger.error(
            f"Order_items load FAILED: {exc}"
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