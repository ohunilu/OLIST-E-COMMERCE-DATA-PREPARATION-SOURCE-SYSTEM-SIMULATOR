"""
Database execution, target preparation, bulk load, and index routines for geolocation.
"""

from __future__ import annotations

import io
import pandas as pd
import psycopg2
from psycopg2 import sql

from geo_util.geo_config import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_SCHEMA,
    DB_USER,
    TARGET_TABLE,
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
    """Ensure target schema exists."""
    logger.info("Ensuring PostgreSQL schema exists: %s", DB_SCHEMA)

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(DB_SCHEMA)
            )
        )


def ensure_table(conn) -> None:
    """Create geolocation table if it does not exist."""
    logger.info(
        "Ensuring target table exists: %s.%s",
        DB_SCHEMA,
        TARGET_TABLE,
    )

    create_table_sql = sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS {}.{} (
            geolocation_zip_code_prefix INTEGER NOT NULL,
            geolocation_lat DOUBLE PRECISION NOT NULL,
            geolocation_lng DOUBLE PRECISION NOT NULL,
            geolocation_city TEXT NOT NULL,
            geolocation_state CHAR(2) NOT NULL
        )
        """
    ).format(
        sql.Identifier(DB_SCHEMA),
        sql.Identifier(TARGET_TABLE),
    )

    with conn.cursor() as cur:
        cur.execute(create_table_sql)

    logger.info("Target table validation/creation passed.")


def bulk_load(conn, df: pd.DataFrame) -> None:
    """Bulk load the DataFrame using PostgreSQL COPY."""
    logger.info(
        "Starting bulk load into %s.%s.",
        DB_SCHEMA,
        TARGET_TABLE,
    )

    columns = [
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
    ]

    buffer = io.StringIO()
    df[columns].to_csv(
        buffer,
        index=False,
        header=False,
        na_rep="\\N",
    )

    buffer.seek(0)

    copy_sql = sql.SQL(
        """
        COPY {}.{} ({})
        FROM STDIN
        WITH CSV
        NULL AS '\\N'
        """
    ).format(
        sql.Identifier(DB_SCHEMA),
        sql.Identifier(TARGET_TABLE),
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
    )

    with conn.cursor() as cur:
        cur.copy_expert(copy_sql.as_string(conn), buffer)

    logger.info("Geolocation bulk load completed successfully.")


def create_indexes(conn) -> None:
    """Create indexes supporting downstream ZIP-code joins."""
    logger.info("Creating geolocation indexes.")

    index_statements = [
        sql.SQL(
            """
            CREATE INDEX IF NOT EXISTS
            idx_geolocation_zip_code_prefix
            ON {}.{} (geolocation_zip_code_prefix)
            """
        ).format(
            sql.Identifier(DB_SCHEMA),
            sql.Identifier(TARGET_TABLE),
        ),
        sql.SQL(
            """
            CREATE INDEX IF NOT EXISTS
            idx_geolocation_state
            ON {}.{} (geolocation_state)
            """
        ).format(
            sql.Identifier(DB_SCHEMA),
            sql.Identifier(TARGET_TABLE),
        ),
    ]

    with conn.cursor() as cur:
        for statement in index_statements:
            cur.execute(statement)

    logger.info("Geolocation indexes created successfully.")