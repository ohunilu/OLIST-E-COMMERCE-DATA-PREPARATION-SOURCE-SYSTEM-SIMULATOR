"""
Database execution engine handling schema creation, COPY operations, and indexing for order_items.
"""

from io import StringIO
import pandas as pd
import psycopg2
from psycopg2 import sql
from ori_util.ori_config import (
    COPY_SQL,
    CREATE_TABLE_SQL,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    SCHEMA_NAME,
    TABLE_NAME,
    OrderItemLoadError,
    logger,
)


def connect_database():
    """Establish and return connection to PostgreSQL target."""
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


def ensure_schema_and_table(conn) -> None:
    """Create target PostgreSQL schema and target table if absent."""
    logger.info("Ensuring PostgreSQL schema exists: %s", SCHEMA_NAME)

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(SCHEMA_NAME)
            )
        )

        logger.info("Ensuring target table exists: %s.%s", SCHEMA_NAME, TABLE_NAME)
        cur.execute(CREATE_TABLE_SQL)

    logger.info("Target table validation/creation passed.")


def bulk_load(conn, df: pd.DataFrame) -> None:
    """Bulk load order items using COPY STDIN via an in-memory CSV buffer."""
    logger.info("Starting bulk load into %s.%s.", SCHEMA_NAME, TABLE_NAME)

    load_df = df.copy()
    load_df["shipping_limit_date"] = load_df["shipping_limit_date"].dt.strftime("%Y-%m-%d %H:%M:%S")

    buffer = StringIO()
    load_df.to_csv(buffer, index=False, header=False, na_rep="\\N")
    buffer.seek(0)

    with conn.cursor() as cur:
        cur.copy_expert(COPY_SQL.as_string(conn), buffer)

    logger.info("Order_items bulk load completed successfully.")


def create_indexes(conn) -> None:
    """Create performance indexes for product, seller, and shipping date columns."""
    logger.info("Creating order-item indexes.")

    index_statements = [
        ("idx_order_items_product_id", "product_id"),
        ("idx_order_items_seller_id", "seller_id"),
        ("idx_order_items_shipping_limit_date", "shipping_limit_date"),
    ]

    with conn.cursor() as cur:
        for idx_name, col_name in index_statements:
            cur.execute(
                sql.SQL(
                    """
                    CREATE INDEX IF NOT EXISTS {}
                    ON {}.{} ({})
                    """
                ).format(
                    sql.Identifier(idx_name),
                    sql.Identifier(SCHEMA_NAME),
                    sql.Identifier(TABLE_NAME),
                    sql.Identifier(col_name),
                )
            )

    logger.info("Order-item indexes created successfully.")