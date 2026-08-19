"""
Database execution routines and COPY loading for reviews data.
"""

from io import StringIO
import pandas as pd
import psycopg2
from psycopg2 import sql
from rev_util.rev_config import (
    COPY_SQL,
    CREATE_TABLE_SQL,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    SCHEMA_NAME,
    TABLE_NAME,
    ReviewLoadError,
    logger,
)


def get_connection():
    """Establish connection to PostgreSQL instance."""
    if not DB_PASSWORD:
        raise ReviewLoadError("POSTGRES_PASSWORD environment variable is not set.")

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


def ensure_target_table(conn) -> None:
    """Ensure target schema and database table exist."""
    logger.info("Ensuring schema exists: %s", SCHEMA_NAME)
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
    """Perform streaming bulk ingestion into target PostgreSQL table using StringIO buffer."""
    logger.info("Starting bulk load into %s.%s.", SCHEMA_NAME, TABLE_NAME)

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

    # Format timestamps explicitly for Postgres COPY engine
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
        cur.copy_expert(
            COPY_SQL.as_string(conn),
            buffer,
        )

    logger.info("Reviews bulk load completed successfully.")


def create_indexes(conn) -> None:
    """Create performance indexes for foreign key lookups, scores, and timestamp queries."""
    logger.info("Creating review indexes.")

    index_queries = [
        ("idx_reviews_order_id", "order_id"),
        ("idx_reviews_score", "review_score"),
        ("idx_reviews_creation_date", "review_creation_date"),
        ("idx_reviews_answer_timestamp", "review_answer_timestamp"),
    ]

    with conn.cursor() as cur:
        for idx_name, column_name in index_queries:
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
                    sql.Identifier(column_name),
                )
            )

    logger.info("Review indexes created successfully.")