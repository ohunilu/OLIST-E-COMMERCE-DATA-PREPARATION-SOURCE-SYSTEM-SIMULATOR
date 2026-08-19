"""
Source DataFrame, cross-table integrity, and target table assertion routines.
"""

from __future__ import annotations

import pandas as pd
from psycopg2 import sql

from pay_util.pay_config import (
    EXPECTED_COLUMNS,
    KNOWN_ZERO_INSTALLMENT_COUNT,
    MAX_INSTALLMENTS,
    ORDERS_TABLE,
    PAYMENT_TYPES,
    SCHEMA_NAME,
    TABLE_NAME,
    logger,
)


def validate_source_schema(df: pd.DataFrame) -> None:
    """Validate that source dataframe matches expected column schema."""
    actual_columns = df.columns.tolist()

    missing_columns = [
        column for column in EXPECTED_COLUMNS if column not in actual_columns
    ]
    unexpected_columns = [
        column for column in actual_columns if column not in EXPECTED_COLUMNS
    ]

    if missing_columns or unexpected_columns:
        raise ValueError(
            "Payments source schema mismatch. "
            f"Missing columns: {missing_columns}; "
            f"Unexpected columns: {unexpected_columns}"
        )

    logger.info("Payments source schema validation passed.")


def validate_required_fields(df: pd.DataFrame) -> None:
    """Validate non-null constraints on required columns."""
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


def validate_composite_key(df: pd.DataFrame) -> None:
    """Validate uniqueness on (order_id, payment_sequential)."""
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


def validate_sequential(df: pd.DataFrame) -> None:
    """Validate payment_sequential bounds."""
    if (df["payment_sequential"] < 1).any():
        invalid_count = (df["payment_sequential"] < 1).sum()
        raise ValueError(
            "Payment sequential validation failed: "
            f"{invalid_count} invalid values."
        )

    logger.info("Payment sequential validation passed.")


def validate_payment_types(df: pd.DataFrame) -> None:
    """Validate allowed enum values for payment_type."""
    actual_payment_types = set(df["payment_type"].dropna().unique())
    unexpected_payment_types = actual_payment_types - PAYMENT_TYPES

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


def validate_installments(df: pd.DataFrame) -> None:
    """Validate payment_installments including known source anomalies."""
    zero_installments = df[df["payment_installments"] == 0]
    invalid_negative = df[df["payment_installments"] < 0]
    above_max = df[df["payment_installments"] > MAX_INSTALLMENTS]

    if len(invalid_negative) > 0:
        raise ValueError(
            "Payments installment validation failed: "
            f"{len(invalid_negative)} negative values."
        )

    if len(above_max) > 0:
        raise ValueError(
            "Payments installment validation failed: "
            f"{len(above_max)} values greater than {MAX_INSTALLMENTS}."
        )

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

        logger.warning("Payment installment anomalies are preserved.")

    logger.info(
        "Payment installments validation passed with "
        "%s known source-data anomaly records.",
        len(zero_installments),
    )


def validate_payment_values(df: pd.DataFrame) -> None:
    """Validate that payment values are non-negative."""
    if (df["payment_value"] < 0).any():
        invalid_count = (df["payment_value"] < 0).sum()
        raise ValueError(
            "Payment value validation failed: "
            f"{invalid_count} negative values."
        )

    logger.info("Payment value validation passed.")


def validate_source_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Run full suite of source Dataframe validation assertions."""
    validate_source_schema(df)
    logger.info("Source records available for loading: %s", len(df))

    validate_required_fields(df)
    validate_composite_key(df)
    validate_sequential(df)
    validate_payment_types(df)
    validate_installments(df)
    validate_payment_values(df)

    return df


def validate_target_is_empty(conn) -> None:
    """Ensure that the target PostgreSQL table is empty."""
    query = sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
        sql.Identifier(SCHEMA_NAME),
        sql.Identifier(TABLE_NAME),
    )

    with conn.cursor() as cur:
        cur.execute(query)
        count = cur.fetchone()[0]

    if count != 0:
        raise ValueError(
            f"Target table {SCHEMA_NAME}.{TABLE_NAME} "
            f"is not empty. Existing records: {count}"
        )

    logger.info("Target table is empty and ready for loading.")


def validate_orders_foreign_key(conn, df: pd.DataFrame) -> None:
    """Pre-load foreign key verification against orders table."""
    logger.info("Validating Payments -> Orders foreign-key relationship.")

    order_ids = set(df["order_id"].astype(str))

    if not order_ids:
        raise ValueError("No order IDs found in payment source.")

    query = sql.SQL(
        "SELECT order_id FROM {}.{} WHERE order_id = ANY(%s)"
    ).format(
        sql.Identifier(SCHEMA_NAME),
        sql.Identifier(ORDERS_TABLE),
    )

    with conn.cursor() as cur:
        cur.execute(query, (list(order_ids),))
        existing_orders = {row[0] for row in cur.fetchall()}

    missing_orders = order_ids - existing_orders

    if missing_orders:
        sample = sorted(missing_orders)[:20]
        raise ValueError(
            "Payments -> Orders foreign-key validation failed. "
            f"Missing order IDs: {len(missing_orders)}. "
            f"Sample: {sample}"
        )

    logger.info("Payments -> Orders foreign-key validation passed.")


def validate_row_count(conn, expected_count: int) -> None:
    """Validate post-load row count matches source count."""
    query = sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
        sql.Identifier(SCHEMA_NAME),
        sql.Identifier(TABLE_NAME),
    )

    with conn.cursor() as cur:
        cur.execute(query)
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


def validate_primary_key(conn) -> None:
    """Validate primary key uniqueness in PostgreSQL after loading."""
    query = sql.SQL(
        """
        SELECT COUNT(*)
        FROM (
            SELECT order_id, payment_sequential
            FROM {}.{}
            GROUP BY order_id, payment_sequential
            HAVING COUNT(*) > 1
        ) duplicates
        """
    ).format(
        sql.Identifier(SCHEMA_NAME),
        sql.Identifier(TABLE_NAME),
    )

    with conn.cursor() as cur:
        cur.execute(query)
        duplicate_groups = cur.fetchone()[0]

    if duplicate_groups > 0:
        raise ValueError(
            "Payment primary-key validation failed: "
            f"{duplicate_groups} duplicate composite keys."
        )

    logger.info("Payment composite-key validation passed.")


def validate_target_required_fields(conn) -> None:
    """Validate non-null constraints on target PostgreSQL table."""
    query = sql.SQL(
        """
        SELECT COUNT(*)
        FROM {}.{}
        WHERE order_id IS NULL
           OR payment_sequential IS NULL
           OR payment_type IS NULL
           OR payment_installments IS NULL
           OR payment_value IS NULL
        """
    ).format(
        sql.Identifier(SCHEMA_NAME),
        sql.Identifier(TABLE_NAME),
    )

    with conn.cursor() as cur:
        cur.execute(query)
        invalid_count = cur.fetchone()[0]

    if invalid_count > 0:
        raise ValueError(
            "Payments required-field validation failed: "
            f"{invalid_count} records contain NULL required fields."
        )

    logger.info("Payments required-field validation passed.")


def validate_foreign_key_after_load(conn) -> None:
    """Post-load foreign key relational integrity validation."""
    logger.info(
        "Validating Payments -> Orders foreign-key relationship after load."
    )

    query = sql.SQL(
        """
        SELECT COUNT(*)
        FROM {schema}.{table} p
        LEFT JOIN {schema}.{orders_table} o
            ON p.order_id = o.order_id
        WHERE o.order_id IS NULL
        """
    ).format(
        schema=sql.Identifier(SCHEMA_NAME),
        table=sql.Identifier(TABLE_NAME),
        orders_table=sql.Identifier(ORDERS_TABLE),
    )

    with conn.cursor() as cur:
        cur.execute(query)
        missing_count = cur.fetchone()[0]

    if missing_count > 0:
        raise ValueError(
            "Payments -> Orders foreign-key validation failed "
            f"after load: {missing_count} orphan records."
        )

    logger.info("Payments -> Orders foreign-key validation passed.")


def validate_installment_anomalies_after_load(conn) -> None:
    """Validate preserved known anomalies and installment ranges on target table."""
    zero_query = sql.SQL(
        """
        SELECT COUNT(*)
        FROM {}.{}
        WHERE payment_installments = 0
        """
    ).format(
        sql.Identifier(SCHEMA_NAME),
        sql.Identifier(TABLE_NAME),
    )

    invalid_query = sql.SQL(
        """
        SELECT COUNT(*)
        FROM {schema}.{table}
        WHERE payment_installments < 0
           OR payment_installments > {max_installments}
        """
    ).format(
        schema=sql.Identifier(SCHEMA_NAME),
        table=sql.Identifier(TABLE_NAME),
        max_installments=sql.Literal(MAX_INSTALLMENTS),
    )

    with conn.cursor() as cur:
        cur.execute(zero_query)
        zero_count = cur.fetchone()[0]

        cur.execute(invalid_query)
        invalid_count = cur.fetchone()[0]

    if zero_count != KNOWN_ZERO_INSTALLMENT_COUNT:
        raise ValueError(
            "Payment installment anomaly preservation validation failed. "
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

    logger.info("Payment installment anomaly preservation validation passed.")