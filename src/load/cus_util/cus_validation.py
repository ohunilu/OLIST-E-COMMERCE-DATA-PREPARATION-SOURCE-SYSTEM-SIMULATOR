"""
Validation routines for checking target table integrity before and after load.
"""

from __future__ import annotations

from psycopg2 import sql

from cus_util.cus_config import TARGET_SCHEMA, TARGET_TABLE, logger
from cus_util.cus_db import get_target_row_count


def validate_target_is_loadable(cursor) -> None:
    """
    Prevent accidental duplicate loads.

    Existing empty table: allowed
    Existing populated table: fail
    """
    row_count = get_target_row_count(cursor)

    if row_count > 0:
        raise RuntimeError(
            f"Target table {TARGET_SCHEMA}.{TARGET_TABLE} already "
            f"contains {row_count:,} records. "
            "Loading has been aborted to prevent duplicate data."
        )

    logger.info("Target table is empty and ready for loading.")


def validate_row_count(cursor, expected_count: int) -> None:
    """Validate source and target row counts."""
    actual_count = get_target_row_count(cursor)

    if actual_count != expected_count:
        raise RuntimeError(
            "Customers row-count validation failed. "
            f"Expected={expected_count:,}, "
            f"Actual={actual_count:,}"
        )

    logger.info(
        "Customers row-count validation passed: %s records.",
        f"{actual_count:,}",
    )


def validate_primary_key(cursor) -> None:
    """Validate that customer_id is populated and unique."""
    cursor.execute(
        sql.SQL(
            """
            SELECT
                COUNT(*) AS total_rows,
                COUNT(customer_id) AS non_null_ids,
                COUNT(DISTINCT customer_id) AS unique_ids
            FROM {}.{}
            """
        ).format(
            sql.Identifier(TARGET_SCHEMA),
            sql.Identifier(TARGET_TABLE),
        )
    )

    total_rows, non_null_ids, unique_ids = cursor.fetchone()

    if non_null_ids != total_rows:
        raise RuntimeError(
            "Customer primary-key validation failed: "
            "NULL customer_id values detected."
        )

    if unique_ids != total_rows:
        raise RuntimeError(
            "Customer primary-key validation failed: "
            "duplicate customer_id values detected."
        )

    logger.info("Customer primary-key validation passed.")


def validate_required_fields(cursor) -> None:
    """Validate required customer fields after loading."""
    required_columns = [
        "customer_id",
        "customer_unique_id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "address_line_1",
        "city",
        "state",
        "zip_code_prefix",
        "country",
        "signup_date",
    ]

    for column in required_columns:
        cursor.execute(
            sql.SQL(
                """
                SELECT COUNT(*)
                FROM {}.{}
                WHERE {} IS NULL
                """
            ).format(
                sql.Identifier(TARGET_SCHEMA),
                sql.Identifier(TARGET_TABLE),
                sql.Identifier(column),
            )
        )

        null_count = cursor.fetchone()[0]

        if null_count != 0:
            raise RuntimeError(
                f"Required field validation failed: "
                f"{column} contains {null_count:,} NULL values."
            )

    logger.info("Customers required-field validation passed.")


def validate_signup_dates(cursor) -> None:
    """Validate that signup_date contains valid temporal values."""
    cursor.execute(
        sql.SQL(
            """
            SELECT
                MIN(signup_date),
                MAX(signup_date),
                COUNT(signup_date)
            FROM {}.{}
            """
        ).format(
            sql.Identifier(TARGET_SCHEMA),
            sql.Identifier(TARGET_TABLE),
        )
    )

    minimum, maximum, non_null_count = cursor.fetchone()

    if non_null_count == 0:
        raise RuntimeError(
            "signup_date validation failed: no populated signup dates."
        )

    logger.info("Customer signup_date validation passed.")
    logger.info(
        "Signup date range: %s to %s",
        minimum,
        maximum,
    )