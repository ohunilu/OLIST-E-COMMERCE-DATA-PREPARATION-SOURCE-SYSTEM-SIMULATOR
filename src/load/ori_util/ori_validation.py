"""
Source pandas validation and target database assertions for order_items data.
"""

import pandas as pd
from psycopg2 import sql
from ori_util.ori_config import (
    EXPECTED_COLUMNS,
    NON_NEGATIVE_COLUMNS,
    NUMERIC_COLUMNS,
    ORDERS_TABLE,
    PRODUCTS_TABLE,
    REQUIRED_COLUMNS,
    SCHEMA_NAME,
    SELLERS_TABLE,
    SOURCE_FILE,
    TABLE_NAME,
    OrderItemLoadError,
    logger,
)


def validate_source_file() -> pd.DataFrame:
    """Validate source file existence, non-emptiness, and structure."""
    if not SOURCE_FILE.exists():
        raise OrderItemLoadError(f"Order_items source file not found: {SOURCE_FILE}")

    if not SOURCE_FILE.is_file():
        raise OrderItemLoadError(f"Order_items source path is not a file: {SOURCE_FILE}")

    logger.info("Order_items source file validation passed.")
    logger.info("Reading order_items source file: %s", SOURCE_FILE)

    df = pd.read_csv(SOURCE_FILE)

    if df.empty:
        raise OrderItemLoadError("Order_items source file is empty.")

    actual_columns = list(df.columns)
    missing = [col for col in EXPECTED_COLUMNS if col not in actual_columns]
    unexpected = [col for col in actual_columns if col not in EXPECTED_COLUMNS]

    if missing or unexpected:
        raise OrderItemLoadError(
            f"Order_items source schema mismatch. Missing: {missing}; Unexpected: {unexpected}"
        )

    if actual_columns != EXPECTED_COLUMNS:
        raise OrderItemLoadError(
            f"Order_items source column order mismatch. Expected: {EXPECTED_COLUMNS}; Actual: {actual_columns}"
        )

    logger.info("Order_items source schema validation passed.")
    logger.info("Source records available for loading: %s", f"{len(df):,}")

    return df


def validate_source_data(df: pd.DataFrame) -> None:
    """Run full in-memory checks across required columns, types, ranges, and sequences."""
    # Required Fields & Blank Strings
    for col in REQUIRED_COLUMNS:
        null_count = df[col].isna().sum()
        if null_count > 0:
            raise OrderItemLoadError(
                f"Order_items required-field validation failed: {col} contains {null_count:,} null values."
            )

        if df[col].dtype == "object":
            blank_count = (df[col].astype(str).str.strip() == "").sum()
            if blank_count > 0:
                raise OrderItemLoadError(
                    f"Order_items required-field validation failed: {col} contains {blank_count:,} blank values."
                )

    logger.info("Order_items required-field validation passed.")

    # Composite Primary Key Check
    duplicate_count = df.duplicated(subset=["order_id", "order_item_id"]).sum()
    if duplicate_count > 0:
        raise OrderItemLoadError(
            f"Order-item composite-key validation failed: {duplicate_count:,} duplicate order_id + order_item_id combinations found."
        )

    logger.info("Order-item composite key validation passed.")

    # Numeric Conversion
    for col in NUMERIC_COLUMNS:
        converted = pd.to_numeric(df[col], errors="coerce")
        invalid_count = converted.isna().sum()
        if invalid_count > 0:
            raise OrderItemLoadError(
                f"Order_items numeric validation failed: {col} contains {invalid_count:,} invalid numeric values."
            )
        df[col] = converted

    logger.info("Order_items numeric value validation passed.")

    # Non-Negative Bounds
    for col in NON_NEGATIVE_COLUMNS:
        invalid_count = (df[col] < 0).sum()
        if invalid_count > 0:
            raise OrderItemLoadError(
                f"Order_items non-negative validation failed: {col} contains {invalid_count:,} negative values."
            )

    logger.info("Order_items non-negative value validation passed.")

    # Timestamp Parsing
    parsed = pd.to_datetime(df["shipping_limit_date"], errors="coerce")
    invalid_ts = parsed.isna().sum()
    if invalid_ts > 0:
        raise OrderItemLoadError(
            f"Order_items timestamp validation failed: {invalid_ts:,} invalid shipping_limit_date values."
        )
    df["shipping_limit_date"] = parsed

    logger.info("Order_items shipping timestamp validation passed.")

    # Sequence Check (Audit / Log Warning for anomalies)
    grouped = (
        df.groupby("order_id")["order_item_id"]
        .apply(lambda vals: sorted(vals.astype(int).tolist()))
    )
    sequence_errors = [
        (order_id, item_ids)
        for order_id, item_ids in grouped.items()
        if item_ids != list(range(1, len(item_ids) + 1))
    ]

    if sequence_errors:
        logger.warning(
            "Order-item sequence validation identified %s orders with non-contiguous order_item_id values. Source sequence structure preserved.",
            f"{len(sequence_errors):,}",
        )
    else:
        logger.info("Order-item sequence validation passed.")


def validate_target_is_empty(conn) -> None:
    """Ensure target order_items table is empty before attempting a bulk COPY."""
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        count = cur.fetchone()[0]

    if count != 0:
        raise OrderItemLoadError(
            f"Target table {SCHEMA_NAME}.{TABLE_NAME} is not empty. Existing records: {count:,}"
        )

    logger.info("Target table is empty and ready for loading.")


def validate_foreign_keys(conn, df: pd.DataFrame) -> None:
    """Ensure referenced orders, products, and sellers exist in PostgreSQL prior to bulk loading."""
    fk_configs = [
        ("Orders", ORDERS_TABLE, "order_id"),
        ("Products", PRODUCTS_TABLE, "product_id"),
        ("Sellers", SELLERS_TABLE, "seller_id"),
    ]

    for label, ref_table, key_col in fk_configs:
        logger.info("Validating Order_items -> %s foreign-key relationship.", label)
        distinct_ids = df[key_col].astype(str).tolist()

        check_sql = sql.SQL(
            """
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT id
                FROM UNNEST(%s::text[]) AS id
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM {schema}.{target_table} target
                    WHERE target.{key_column} = id
                )
            ) missing
            """
        ).format(
            schema=sql.Identifier(SCHEMA_NAME),
            target_table=sql.Identifier(ref_table),
            key_column=sql.Identifier(key_col),
        )

        with conn.cursor() as cur:
            cur.execute(check_sql, (distinct_ids,))
            missing_count = cur.fetchone()[0]

        if missing_count > 0:
            raise OrderItemLoadError(
                f"Order_items -> {label} foreign-key validation failed: {missing_count:,} {key_col} references are missing."
            )

        logger.info("Order_items -> %s foreign-key validation passed.", label)


def validate_loaded_data(conn, expected_count: int) -> None:
    """Perform database assertions on target table post bulk loading."""
    with conn.cursor() as cur:
        # Row Count Verification
        cur.execute(
            sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        actual_count = cur.fetchone()[0]
        if actual_count != expected_count:
            raise OrderItemLoadError(
                f"Order_items row-count validation failed: expected {expected_count:,}, found {actual_count:,}."
            )
        logger.info("Order_items row-count validation passed: %s records.", f"{actual_count:,}")

        # Duplicate Composite Key Audit
        cur.execute(
            sql.SQL(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT order_id, order_item_id
                    FROM {schema}.{table}
                    GROUP BY order_id, order_item_id
                    HAVING COUNT(*) > 1
                ) duplicates
                """
            ).format(
                schema=sql.Identifier(SCHEMA_NAME),
                table=sql.Identifier(TABLE_NAME),
            )
        )
        duplicates = cur.fetchone()[0]
        if duplicates > 0:
            raise OrderItemLoadError(
                f"Order-item composite-key validation failed after load: {duplicates:,} duplicate keys found."
            )
        logger.info("Order-item composite-key validation passed.")

        # Required Fields Non-Null Checks
        cur.execute(
            sql.SQL(
                """
                SELECT
                    COUNT(*) FILTER (WHERE order_id IS NULL),
                    COUNT(*) FILTER (WHERE order_item_id IS NULL),
                    COUNT(*) FILTER (WHERE product_id IS NULL),
                    COUNT(*) FILTER (WHERE seller_id IS NULL),
                    COUNT(*) FILTER (WHERE shipping_limit_date IS NULL),
                    COUNT(*) FILTER (WHERE price IS NULL),
                    COUNT(*) FILTER (WHERE freight_value IS NULL)
                FROM {schema}.{table}
                """
            ).format(
                schema=sql.Identifier(SCHEMA_NAME),
                table=sql.Identifier(TABLE_NAME),
            )
        )
        null_counts = cur.fetchone()
        if any(null_counts):
            raise OrderItemLoadError(
                f"Order_items required-field validation failed after load: null counts = {null_counts}"
            )
        logger.info("Order_items required-field validation passed.")

        # Post-Load Foreign Key Checks
        fk_verifications = [
            ("Orders", ORDERS_TABLE, "order_id"),
            ("Products", PRODUCTS_TABLE, "product_id"),
            ("Sellers", SELLERS_TABLE, "seller_id"),
        ]

        for label, ref_table, key_col in fk_verifications:
            fk_sql = sql.SQL(
                """
                SELECT COUNT(*)
                FROM {schema}.{table} item
                LEFT JOIN {schema}.{ref_table} ref ON item.{key_col} = ref.{key_col}
                WHERE ref.{key_col} IS NULL
                """
            ).format(
                schema=sql.Identifier(SCHEMA_NAME),
                table=sql.Identifier(TABLE_NAME),
                ref_table=sql.Identifier(ref_table),
                key_col=sql.Identifier(key_col),
            )
            cur.execute(fk_sql)
            missing = cur.fetchone()[0]
            if missing > 0:
                raise OrderItemLoadError(
                    f"Order_items -> {label} foreign-key validation failed after load: {missing:,} missing references."
                )

        logger.info("Order_items foreign-key validation passed after load.")