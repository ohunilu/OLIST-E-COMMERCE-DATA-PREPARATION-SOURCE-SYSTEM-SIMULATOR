"""
Source pandas checks and target database validation rules for reviews data.
"""

import pandas as pd
from psycopg2 import sql
from rev_util.rev_config import (
    EXPECTED_COLUMNS,
    MAX_REVIEW_SCORE,
    MIN_REVIEW_SCORE,
    ORDERS_TABLE,
    REQUIRED_COLUMNS,
    SCHEMA_NAME,
    SOURCE_FILE,
    TABLE_NAME,
    ReviewLoadError,
    logger,
)


def validate_source_file() -> pd.DataFrame:
    """Read and validate the source reviews CSV file."""
    logger.info("Reading reviews source file: %s", SOURCE_FILE)

    if not SOURCE_FILE.exists():
        raise ReviewLoadError(f"Reviews source file not found: {SOURCE_FILE}")

    if SOURCE_FILE.stat().st_size == 0:
        raise ReviewLoadError(f"Reviews source file is empty: {SOURCE_FILE}")

    logger.info("Reviews source file validation passed.")

    df = pd.read_csv(SOURCE_FILE)

    # Schema Validation
    actual_columns = df.columns.tolist()
    missing = [c for c in EXPECTED_COLUMNS if c not in actual_columns]
    unexpected = [c for c in actual_columns if c not in EXPECTED_COLUMNS]

    if missing or unexpected:
        raise ReviewLoadError(
            f"Reviews schema mismatch. Missing: {missing}; Unexpected: {unexpected}"
        )

    logger.info("Reviews source schema validation passed.")
    logger.info("Source records available for loading: %s", f"{len(df):,}")

    if len(df) == 0:
        raise ReviewLoadError("Reviews source file contains zero records.")

    # Required Fields Validation
    null_counts = df[REQUIRED_COLUMNS].isna().sum()
    invalid_nulls = null_counts[null_counts > 0]
    if not invalid_nulls.empty:
        raise ReviewLoadError(f"Reviews required-field validation failed: {invalid_nulls.to_dict()}")

    logger.info("Reviews required-field validation passed.")

    # Composite Key Validation
    duplicate_keys = int(df.duplicated(["review_id", "order_id"]).sum())
    if duplicate_keys > 0:
        raise ReviewLoadError(
            f"Review composite-key validation failed: {duplicate_keys:,} duplicate review_id + order_id pairs."
        )

    logger.info("Review composite-key validation passed.")

    # Uniqueness Model Logging
    duplicate_review_ids = int(df["review_id"].duplicated().sum())
    if duplicate_review_ids > 0:
        logger.info(
            "Review uniqueness model validated: review_id alone is non-unique (%s duplicates); composite key is unique.",
            f"{duplicate_review_ids:,}",
        )
    else:
        logger.info("Review ID validation passed: review_id values are strictly unique.")

    # Score Range Validation
    invalid_scores = df[
        (df["review_score"] < MIN_REVIEW_SCORE) | (df["review_score"] > MAX_REVIEW_SCORE)
    ]
    if len(invalid_scores) > 0:
        raise ReviewLoadError(
            f"Review score validation failed: {len(invalid_scores):,} invalid values. Expected range: {MIN_REVIEW_SCORE}-{MAX_REVIEW_SCORE}."
        )

    logger.info("Review score validation passed.")
    logger.info("Review score distribution: %s", df["review_score"].value_counts().sort_index().to_dict())

    # Timestamp Parsing Validation
    creation_ts = pd.to_datetime(df["review_creation_date"], errors="coerce")
    answer_ts = pd.to_datetime(df["review_answer_timestamp"], errors="coerce")

    if creation_ts.isna().any():
        raise ReviewLoadError(f"Review creation timestamp validation failed: {creation_ts.isna().sum():,} invalid timestamps.")

    if answer_ts.isna().any():
        raise ReviewLoadError(f"Review answer timestamp validation failed: {answer_ts.isna().sum():,} invalid timestamps.")

    logger.info("Review timestamp parsing validation passed.")

    # Chronology Check
    chronology_violations = int((creation_ts > answer_ts).sum())
    if chronology_violations > 0:
        raise ReviewLoadError(
            f"Review chronology validation failed: review_creation_date > review_answer_timestamp in {chronology_violations:,} records."
        )

    logger.info("Review chronology validation passed: creation <= answer.")
    logger.info("Review creation timestamp range: %s to %s", creation_ts.min(), creation_ts.max())
    logger.info("Review answer timestamp range: %s to %s", answer_ts.min(), answer_ts.max())

    return df


def validate_target_is_empty(conn) -> None:
    """Ensure target reviews table is empty before insertion."""
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        count = cur.fetchone()[0]

    if count != 0:
        raise ReviewLoadError(
            f"Target table {SCHEMA_NAME}.{TABLE_NAME} is not empty. Existing records: {count:,}"
        )

    logger.info("Target table is empty and ready for loading.")


def validate_orders_foreign_key(conn, df: pd.DataFrame) -> None:
    """Ensure all referenced order_ids exist in the target orders table prior to loading."""
    logger.info("Validating Reviews -> Orders foreign-key relationship.")
    order_ids = list(set(df["order_id"].astype(str)))

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("SELECT order_id FROM {}.{} WHERE order_id = ANY(%s)").format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(ORDERS_TABLE),
            ),
            (order_ids,),
        )
        existing_orders = {row[0] for row in cur.fetchall()}

    missing_orders = set(order_ids) - existing_orders
    if missing_orders:
        sample = sorted(list(missing_orders))[:20]
        raise ReviewLoadError(
            f"Reviews -> Orders FK validation failed. Missing order IDs: {len(missing_orders):,}. Sample: {sample}"
        )

    logger.info("Reviews -> Orders foreign-key validation passed.")


def validate_loaded_data(conn, expected_count: int) -> None:
    """Execute post-load validations on the target database table."""
    with conn.cursor() as cur:
        # Row count check
        cur.execute(
            sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        actual_count = cur.fetchone()[0]
        if actual_count != expected_count:
            raise ReviewLoadError(
                f"Reviews row-count validation failed: expected {expected_count:,}, found {actual_count:,}."
            )
        logger.info("Reviews row-count validation passed: %s records.", f"{actual_count:,}")

        # Primary key uniqueness check
        cur.execute(
            sql.SQL(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT review_id, order_id
                    FROM {}.{}
                    GROUP BY review_id, order_id
                    HAVING COUNT(*) > 1
                ) duplicates
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        if cur.fetchone()[0] > 0:
            raise ReviewLoadError("Review composite-key validation failed in database after load.")
        logger.info("Review composite-key post-load validation passed.")

        # Required fields check
        cur.execute(
            sql.SQL(
                """
                SELECT COUNT(*)
                FROM {}.{}
                WHERE review_id IS NULL
                   OR order_id IS NULL
                   OR review_score IS NULL
                   OR review_creation_date IS NULL
                   OR review_answer_timestamp IS NULL
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        if cur.fetchone()[0] > 0:
            raise ReviewLoadError("Reviews required-field validation failed after load: NULLs detected.")
        logger.info("Reviews required-field post-load validation passed.")

        # Foreign key integrity check
        cur.execute(
            sql.SQL(
                """
                SELECT COUNT(*)
                FROM {}.{} r
                LEFT JOIN {}.{} o ON r.order_id = o.order_id
                WHERE o.order_id IS NULL
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(ORDERS_TABLE),
            )
        )
        orphans = cur.fetchone()[0]
        if orphans > 0:
            raise ReviewLoadError(f"Reviews -> Orders FK validation failed after load: {orphans:,} orphan records.")
        logger.info("Reviews -> Orders foreign-key post-load validation passed.")

        # Score boundary check
        cur.execute(
            sql.SQL(
                """
                SELECT COUNT(*)
                FROM {}.{}
                WHERE review_score < %s OR review_score > %s
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            ),
            (MIN_REVIEW_SCORE, MAX_REVIEW_SCORE),
        )
        if cur.fetchone()[0] > 0:
            raise ReviewLoadError("Review score range validation failed after load.")
        logger.info("Review score range post-load validation passed.")

        # Chronology check
        cur.execute(
            sql.SQL(
                """
                SELECT COUNT(*)
                FROM {}.{}
                WHERE review_creation_date > review_answer_timestamp
                """
            ).format(
                sql.Identifier(SCHEMA_NAME),
                sql.Identifier(TABLE_NAME),
            )
        )
        if cur.fetchone()[0] > 0:
            raise ReviewLoadError("Review chronology validation failed after load.")
        logger.info("Review chronology post-load validation passed.")