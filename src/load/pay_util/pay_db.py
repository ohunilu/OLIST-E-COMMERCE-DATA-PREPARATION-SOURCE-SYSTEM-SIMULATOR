"""
Database execution, target schema creation, bulk load, and index routines for payments.
"""

from __future__ import annotations

import io
import pandas as pd
import psycopg2
from psycopg2 import sql

from pay_util.pay_config import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    MAX_INSTALLMENTS,
    ORDERS_TABLE,
    SCHEMA_NAME,
    TABLE_NAME,
    logger,
)


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


def ensure_schema(conn) -> None:
    """Ensure target PostgreSQL schema exists."""
    logger.info("Ensuring PostgreSQL schema exists: %s", SCHEMA_NAME)

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(SCHEMA_NAME)
            )
        )

    conn.commit()


def ensure_target_table(conn) -> None:
    """Create and validate public.payments."""
    logger.info(
        "Ensuring target table exists: %s.%s",
        SCHEMA_NAME,
        TABLE_NAME,
    )

    create_sql = sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS {schema}.{table} (
            order_id TEXT NOT NULL,
            payment_sequential INTEGER NOT NULL,
            payment_type TEXT NOT NULL,
            payment_installments INTEGER NOT NULL,
            payment_value NUMERIC(12, 2) NOT NULL,

            CONSTRAINT payments_pkey
                PRIMARY KEY (order_id, payment_sequential),

            CONSTRAINT payments_order_fk
                FOREIGN KEY (order_id)
                REFERENCES {schema}.{orders_table}(order_id),

            CONSTRAINT payments_installments_max_chk
                CHECK (payment_installments <= {max_installments}),

            CONSTRAINT payments_value_nonnegative_chk
                CHECK (payment_value >= 0)
        )
        """
    ).format(
        schema=sql.Identifier(SCHEMA_NAME),
        table=sql.Identifier(TABLE_NAME),
        orders_table=sql.Identifier(ORDERS_TABLE),
        max_installments=sql.Literal(MAX_INSTALLMENTS),
    )

    with conn.cursor() as cur:
        cur.execute(create_sql)

    logger.info("Target table validation/creation passed.")


def bulk_load(conn, df: pd.DataFrame) -> None:
    """Bulk load DataFrame into PostgreSQL payments table."""
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

    buffer = io.StringIO()
    df[load_columns].to_csv(
        buffer,
        index=False,
        header=False,
        na_rep="\\N",
    )

    buffer.seek(0)

    copy_sql = sql.SQL(
        """
        COPY {schema}.{table}
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
    ).format(
        schema=sql.Identifier(SCHEMA_NAME),
        table=sql.Identifier(TABLE_NAME),
    )

    with conn.cursor() as cur:
        cur.copy_expert(copy_sql.as_string(conn), buffer)

    logger.info("Payments bulk load completed successfully.")


def create_indexes(conn) -> None:
    """Create performance indexes on public.payments."""
    logger.info("Creating payment indexes.")

    index_statements = [
        sql.SQL(
            """
            CREATE INDEX IF NOT EXISTS idx_payments_order_id
            ON {}.{}(order_id)
            """
        ).format(
            sql.Identifier(SCHEMA_NAME),
            sql.Identifier(TABLE_NAME),
        ),
        sql.SQL(
            """
            CREATE INDEX IF NOT EXISTS idx_payments_type
            ON {}.{}(payment_type)
            """
        ).format(
            sql.Identifier(SCHEMA_NAME),
            sql.Identifier(TABLE_NAME),
        ),
        sql.SQL(
            """
            CREATE INDEX IF NOT EXISTS idx_payments_sequential
            ON {}.{}(payment_sequential)
            """
        ).format(
            sql.Identifier(SCHEMA_NAME),
            sql.Identifier(TABLE_NAME),
        ),
    ]

    with conn.cursor() as cur:
        for statement in index_statements:
            cur.execute(statement)

    logger.info("Payment indexes created successfully.")