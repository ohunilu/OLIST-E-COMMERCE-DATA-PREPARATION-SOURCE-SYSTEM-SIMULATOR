"""
Source pandas checks and target database validation rules for orders data.
"""

import pandas as pd
from psycopg2 import sql
from ord_util.ord_config import (
    CUSTOMERS_TABLE,
    EXPECTED_COLUMNS,
    REQUIRED_COLUMNS,
    SCHEMA_NAME,
    SOURCE_FILE,
    TABLE_NAME,
    TIMESTAMP_COLUMNS,
    OrderLoadError,
    logger,
)


def validate_source_file() -> pd.DataFrame:
    """Read and validate the source orders CSV file."""
    logger.info("Reading orders source file: %s", SOURCE_FILE)

    if not SOURCE_FILE.exists():
        raise OrderLoadError(f"Orders source file does not exist: {SOURCE_FILE}")

    df = pd.read_csv(SOURCE_FILE)

    if df.empty:
        raise OrderLoadError("Orders source file is empty.")

    logger.info("Orders source file validation passed.")

    actual_columns = df.columns.tolist()
    if actual_columns != EXPECTED_COLUMNS:
        raise OrderLoadError(
            f"Orders source schema mismatch.\nExpected: {EXPECTED_COLUMNS}\nActual: {actual_columns}"
        )

    logger.info("Orders source schema validation passed.")
    logger.info("Source records available for loading: %s", f"{len(df):,}")

    return df


def validate_source_data(df: pd.DataFrame) -> None:
    """Validate primary key, required fields, timestamps, and chronology in source dataframe."""
    # Primary Key
    if df["order_id"].isna().any():
        raise OrderLoadError("Orders contain NULL order_id values.")

    duplicate_order_ids = int(df["order_id"].duplicated().sum())
    if duplicate_order_ids > 0:
        raise OrderLoadError(f"Orders contain {duplicate_order_ids:,} duplicate order_id values.")

    logger.info("Order primary-key validation passed.")

    # Required Fields
    null_counts = df[REQUIRED_COLUMNS].isna().sum()
    if null_counts.any():
        raise OrderLoadError(
            f"Orders contain NULL values in required fields:\n{null_counts[null_counts > 0]}"
        )

    logger.info("Orders required-field validation passed.")

    # Timestamp Parsing
    for column in TIMESTAMP_COLUMNS:
        parsed = pd.to_datetime(df[column], errors="coerce")
        invalid_mask = df[column].notna() & parsed.isna()

        if invalid_mask.any():
            raise OrderLoadError(
                f"Orders contain invalid timestamps in {column}: {invalid_mask.sum():,} records."
            )

        df[column] = parsed

    logger.info("Order timestamp parsing validation passed.")

    # Purchase Timestamp Validation
    if df["order_purchase_timestamp"].isna().any():
        raise OrderLoadError("Orders contain NULL order_purchase_timestamp values.")

    logger.info(
        "Order purchase timestamp range: %s to %s",
        df["order_purchase_timestamp"].min(),
        df["order_purchase_timestamp"].max(),
    )

    # Chronology Check (Soft validation for known source anomalies)
    chronology_checks = [
        ("order_purchase_timestamp", "order_approved_at", "purchase <= approved"),
        ("order_approved_at", "order_delivered_carrier_date", "approved <= carrier"),
        ("order_delivered_carrier_date", "order_delivered_customer_date", "carrier <= customer delivery"),
    ]

    total_chronology_violations = 0
    for earlier, later, description in chronology_checks:
        mask = df[earlier].notna() & df[later].notna() & (df[earlier] > df[later])
        violations = int(mask.sum())

        if violations > 0:
            total_chronology_violations += violations
            logger.warning(
                "Known source chronology anomaly: %s violated in %s records.",
                description,
                f"{violations:,}",
            )
        else:
            logger.info("Order chronology check passed: %s.", description)

    logger.warning(
        "Order chronology validation completed with %s known source-data anomaly records. Anomalies are preserved.",
        f"{total_chronology_violations:,}",
    )

    # Estimated Delivery Validation
    invalid_estimates = (
        df["order_estimated_delivery_date"].notna()
        & (df["order_estimated_delivery_date"] < df["order_purchase_timestamp"])
    )

    if invalid_estimates.any():
        raise OrderLoadError(
            f"Estimated delivery date occurs before purchase timestamp in {invalid_estimates.sum():,} records."
        )

    logger.info("Order estimated-delivery validation passed.")


def validate_target_is_empty(conn) -> None:
    """Ensure target orders table is empty before copying."""
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        count = cur.fetchone()[0]

    if count > 0:
        raise OrderLoadError(
            f"Target table {SCHEMA_NAME}.{TABLE_NAME} already contains {count:,} records. Loader will not overwrite."
        )

    logger.info("Target table is empty and ready for loading.")


def validate_customer_references(conn, df: pd.DataFrame) -> None:
    """Ensure all customer_ids exist in the target customers table prior to load."""
    logger.info("Validating Orders -> Customers foreign-key relationship.")
    source_customer_ids = set(df["customer_id"].astype(str))

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("SELECT customer_id FROM {}.{} WHERE customer_id = ANY(%s)").format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(CUSTOMERS_TABLE),
            ),
            (list(source_customer_ids),),
        )
        existing_customer_ids = {row[0] for row in cur.fetchall()}

    missing = source_customer_ids - existing_customer_ids
    if missing:
        sample = sorted(list(missing))[:20]
        raise OrderLoadError(
            f"Orders contain customer_id values that do not exist in {SCHEMA_NAME}.{CUSTOMERS_TABLE}.\n"
            f"Missing customer IDs: {len(missing):,}\nSample: {sample}"
        )

    logger.info("Orders -> Customers foreign-key validation passed.")


def validate_target(conn, source_count: int) -> None:
    """Perform post-load assertions on target PostgreSQL table."""
    with conn.cursor() as cur:
        # Row Count Check
        cur.execute(
            sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        target_count = cur.fetchone()[0]
        if target_count != source_count:
            raise OrderLoadError(
                f"Orders row-count validation failed: source={source_count:,}, target={target_count:,}"
            )
        logger.info("Orders row-count validation passed: %s records.", f"{target_count:,}")

        # Primary Key Uniqueness Check
        cur.execute(
            sql.SQL("SELECT COUNT(*), COUNT(DISTINCT order_id) FROM {}.{}").format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        total, unique_ids = cur.fetchone()
        if total != unique_ids:
            raise OrderLoadError(f"Order primary-key validation failed: total={total:,}, unique={unique_ids:,}")
        logger.info("Order primary-key validation passed.")

        # Required Fields Check
        cur.execute(
            sql.SQL(
                """
                SELECT
                    COUNT(*) FILTER (WHERE order_id IS NULL),
                    COUNT(*) FILTER (WHERE customer_id IS NULL),
                    COUNT(*) FILTER (WHERE order_status IS NULL),
                    COUNT(*) FILTER (WHERE order_purchase_timestamp IS NULL)
                FROM {}.{}
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        null_counts = cur.fetchone()
        if any(null_counts):
            raise OrderLoadError(f"Orders required-field validation failed: {null_counts}")
        logger.info("Orders required-field validation passed.")

        # Foreign Key Foreign Orphan Check
        cur.execute(
            sql.SQL(
                """
                SELECT COUNT(*)
                FROM {}.{} o
                LEFT JOIN {}.{} c ON o.customer_id = c.customer_id
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
            raise OrderLoadError(f"Orders -> Customers foreign-key validation failed: {orphan_count:,} orphan records.")
        logger.info("Orders -> Customers foreign-key validation passed.")

        # Timestamp Range Logging
        cur.execute(
            sql.SQL(
                """
                SELECT MIN(order_purchase_timestamp), MAX(order_purchase_timestamp)
                FROM {}.{}
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        ts_min, ts_max = cur.fetchone()
        logger.info("Order purchase timestamp range: %s to %s", ts_min, ts_max)

        # Target Chronology Audit
        cur.execute(
            sql.SQL(
                """
                SELECT COUNT(*)
                FROM {}.{}
                WHERE
                    (order_approved_at IS NOT NULL AND order_purchase_timestamp > order_approved_at)
                    OR (order_approved_at IS NOT NULL AND order_delivered_carrier_date IS NOT NULL AND order_approved_at > order_delivered_carrier_date)
                    OR (order_delivered_carrier_date IS NOT NULL AND order_delivered_customer_date IS NOT NULL AND order_delivered_carrier_date > order_delivered_customer_date)
                    OR (order_estimated_delivery_date IS NOT NULL AND order_estimated_delivery_date < order_purchase_timestamp)
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        chronology_violations = cur.fetchone()[0]
        if chronology_violations > 0:
            logger.warning(
                "Target order chronology contains %s known source-data anomaly records. Anomalies were preserved during loading.",
                f"{chronology_violations:,}",
            )
        else:
            logger.info("Target order chronology validation passed.")