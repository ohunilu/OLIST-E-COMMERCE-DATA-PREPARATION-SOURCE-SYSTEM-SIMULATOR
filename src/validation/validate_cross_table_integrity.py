"""
Cross-table integrity validation for the Olist prepared datasets.

This module validates referential integrity, key uniqueness, row-count
expectations, and important cross-table relationships across the
transformed Olist datasets.

The validator is intentionally read-only. It does not modify any
prepared dataset.

Expected prepared datasets:

    customers.csv
    orders.csv
    order_items.csv
    products.csv
    payments.csv
    sellers.csv
    reviews.csv
    geolocation.csv

Usage:

    docker compose exec preparation \
        python src/validate/validate_cross_table_integrity.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path("/app")
SIMULATED_DATA_DIR = BASE_DIR / "simulated_data"

FILES = {
    "customers": SIMULATED_DATA_DIR / "customers.csv",
    "orders": SIMULATED_DATA_DIR / "orders.csv",
    "order_items": SIMULATED_DATA_DIR / "order_items.csv",
    "products": SIMULATED_DATA_DIR / "products.csv",
    "payments": SIMULATED_DATA_DIR / "payments.csv",
    "sellers": SIMULATED_DATA_DIR / "sellers.csv",
    "reviews": SIMULATED_DATA_DIR / "reviews.csv",
    "geolocation": SIMULATED_DATA_DIR / "geolocation.csv",
}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CrossTableValidationError(Exception):
    """Raised when cross-table integrity validation fails."""


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def load_dataset(name: str, path: Path) -> pd.DataFrame:
    """Load a prepared dataset and validate that the file exists."""

    if not path.exists():
        raise CrossTableValidationError(
            f"Required dataset not found: {path}"
        )

    logger.info("Reading %s: %s", name, path)

    df = pd.read_csv(path)

    logger.info(
        "%s records loaded: %s",
        name.capitalize(),
        f"{len(df):,}",
    )

    return df


def validate_required_columns(
    name: str,
    df: pd.DataFrame,
    required_columns: Iterable[str],
) -> None:
    """Validate that all required columns exist."""

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise CrossTableValidationError(
            f"{name} is missing required columns: {missing}"
        )

    logger.info(
        "%s required-column validation passed.",
        name.capitalize(),
    )


def validate_unique_key(
    name: str,
    df: pd.DataFrame,
    columns: list[str],
) -> None:
    """Validate uniqueness of a business key."""

    duplicate_count = df.duplicated(columns).sum()

    if duplicate_count > 0:
        raise CrossTableValidationError(
            f"{name} key validation failed: "
            f"{duplicate_count:,} duplicate records found "
            f"for key {columns}."
        )

    logger.info(
        "%s unique-key validation passed: %s.",
        name.capitalize(),
        " + ".join(columns),
    )


def validate_no_nulls(
    name: str,
    df: pd.DataFrame,
    columns: Iterable[str],
) -> None:
    """Validate that key columns do not contain NULL values."""

    null_counts = df[list(columns)].isna().sum()

    failures = {
        column: int(count)
        for column, count in null_counts.items()
        if count > 0
    }

    if failures:
        raise CrossTableValidationError(
            f"{name} contains NULL values in key columns: {failures}"
        )

    logger.info(
        "%s key NULL validation passed.",
        name.capitalize(),
    )


def validate_foreign_key(
    child_name: str,
    child_df: pd.DataFrame,
    child_column: str,
    parent_name: str,
    parent_df: pd.DataFrame,
    parent_column: str,
) -> int:
    """
    Validate that every non-null child foreign key exists in the parent.

    Returns:
        Number of orphan records.
    """

    child_values = child_df[child_column].dropna()
    parent_values = parent_df[parent_column].dropna()

    orphan_mask = ~child_values.isin(parent_values)
    orphan_count = int(orphan_mask.sum())

    if orphan_count > 0:
        orphan_values = (
            child_values[orphan_mask]
            .drop_duplicates()
            .head(10)
            .tolist()
        )

        raise CrossTableValidationError(
            f"Referential integrity failed: "
            f"{child_name}.{child_column} contains "
            f"{orphan_count:,} orphan records referencing "
            f"{parent_name}.{parent_column}. "
            f"Sample orphan values: {orphan_values}"
        )

    logger.info(
        "Referential integrity passed: "
        "%s.%s -> %s.%s",
        child_name,
        child_column,
        parent_name,
        parent_column,
    )

    return orphan_count


def validate_optional_foreign_key(
    child_name: str,
    child_df: pd.DataFrame,
    child_column: str,
    parent_name: str,
    parent_df: pd.DataFrame,
    parent_column: str,
) -> None:
    """
    Validate a foreign-key relationship but report orphan values as a
    warning rather than failing the complete validation.

    This is appropriate for source-system geographic relationships,
    where a source ZIP prefix may not have a corresponding geolocation
    observation.
    """

    child_values = child_df[child_column].dropna()
    parent_values = parent_df[parent_column].dropna()

    orphan_mask = ~child_values.isin(parent_values)
    orphan_count = int(orphan_mask.sum())

    if orphan_count > 0:
        orphan_values = (
            child_values[orphan_mask]
            .drop_duplicates()
            .head(10)
            .tolist()
        )

        logger.warning(
            "Geographic reference anomaly: "
            "%s.%s contains %s records whose value does not "
            "exist in %s.%s. Sample values: %s",
            child_name,
            child_column,
            f"{orphan_count:,}",
            parent_name,
            parent_column,
            orphan_values,
        )

        return

    logger.info(
        "Geographic referential integrity passed: "
        "%s.%s -> %s.%s",
        child_name,
        child_column,
        parent_name,
        parent_column,
    )


def validate_row_count(
    name: str,
    df: pd.DataFrame,
    expected_minimum: int = 1,
) -> None:
    """Validate that a prepared dataset is not unexpectedly empty."""

    if len(df) < expected_minimum:
        raise CrossTableValidationError(
            f"{name} contains only {len(df):,} records."
        )

    logger.info(
        "%s row-count validation passed: %s records.",
        name.capitalize(),
        f"{len(df):,}",
    )


# ---------------------------------------------------------------------------
# Dataset-level validation
# ---------------------------------------------------------------------------


def validate_dataset_keys(datasets: dict[str, pd.DataFrame]) -> None:
    """Validate primary and composite keys for all prepared datasets."""

    validate_unique_key(
        "Customers",
        datasets["customers"],
        ["customer_id"],
    )

    validate_unique_key(
        "Orders",
        datasets["orders"],
        ["order_id"],
    )

    validate_unique_key(
        "Order items",
        datasets["order_items"],
        ["order_id", "order_item_id"],
    )

    validate_unique_key(
        "Products",
        datasets["products"],
        ["product_id"],
    )

    validate_unique_key(
        "Payments",
        datasets["payments"],
        ["order_id", "payment_sequential"],
    )

    validate_unique_key(
        "Sellers",
        datasets["sellers"],
        ["seller_id"],
    )

    validate_unique_key(
        "Reviews",
        datasets["reviews"],
        ["review_id", "order_id"],
    )


def validate_key_nulls(datasets: dict[str, pd.DataFrame]) -> None:
    """Validate NULL-free relationship keys."""

    validate_no_nulls(
        "Customers",
        datasets["customers"],
        ["customer_id"],
    )

    validate_no_nulls(
        "Orders",
        datasets["orders"],
        ["order_id", "customer_id"],
    )

    validate_no_nulls(
        "Order items",
        datasets["order_items"],
        [
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
        ],
    )

    validate_no_nulls(
        "Products",
        datasets["products"],
        ["product_id"],
    )

    validate_no_nulls(
        "Payments",
        datasets["payments"],
        ["order_id", "payment_sequential"],
    )

    validate_no_nulls(
        "Sellers",
        datasets["sellers"],
        ["seller_id"],
    )

    validate_no_nulls(
        "Reviews",
        datasets["reviews"],
        ["review_id", "order_id"],
    )

    validate_no_nulls(
        "Geolocation",
        datasets["geolocation"],
        ["geolocation_zip_code_prefix"],
    )


# ---------------------------------------------------------------------------
# Referential integrity
# ---------------------------------------------------------------------------


def validate_referential_integrity(
    datasets: dict[str, pd.DataFrame],
) -> None:
    """Validate all critical cross-table foreign-key relationships."""

    logger.info("Starting critical referential-integrity validation.")

    # ------------------------------------------------------------------
    # Orders -> Customers
    # ------------------------------------------------------------------

    validate_foreign_key(
        child_name="orders",
        child_df=datasets["orders"],
        child_column="customer_id",
        parent_name="customers",
        parent_df=datasets["customers"],
        parent_column="customer_id",
    )

    # ------------------------------------------------------------------
    # Order Items -> Orders
    # ------------------------------------------------------------------

    validate_foreign_key(
        child_name="order_items",
        child_df=datasets["order_items"],
        child_column="order_id",
        parent_name="orders",
        parent_df=datasets["orders"],
        parent_column="order_id",
    )

    # ------------------------------------------------------------------
    # Order Items -> Products
    # ------------------------------------------------------------------

    validate_foreign_key(
        child_name="order_items",
        child_df=datasets["order_items"],
        child_column="product_id",
        parent_name="products",
        parent_df=datasets["products"],
        parent_column="product_id",
    )

    # ------------------------------------------------------------------
    # Order Items -> Sellers
    # ------------------------------------------------------------------

    validate_foreign_key(
        child_name="order_items",
        child_df=datasets["order_items"],
        child_column="seller_id",
        parent_name="sellers",
        parent_df=datasets["sellers"],
        parent_column="seller_id",
    )

    # ------------------------------------------------------------------
    # Payments -> Orders
    # ------------------------------------------------------------------

    validate_foreign_key(
        child_name="payments",
        child_df=datasets["payments"],
        child_column="order_id",
        parent_name="orders",
        parent_df=datasets["orders"],
        parent_column="order_id",
    )

    # ------------------------------------------------------------------
    # Reviews -> Orders
    # ------------------------------------------------------------------

    validate_foreign_key(
        child_name="reviews",
        child_df=datasets["reviews"],
        child_column="order_id",
        parent_name="orders",
        parent_df=datasets["orders"],
        parent_column="order_id",
    )

    logger.info(
        "Critical referential-integrity validation passed."
    )


# ---------------------------------------------------------------------------
# Geographic integrity
# ---------------------------------------------------------------------------


def validate_geographic_references(
    datasets: dict[str, pd.DataFrame],
) -> None:
    """
    Validate customer/seller ZIP-prefix relationships against geolocation.

    Geographic relationships are warnings rather than hard failures because
    the Olist source data can contain ZIP prefixes that are not represented
    in the geolocation observation table.
    """

    logger.info(
        "Starting geographic referential-integrity validation."
    )

    geolocation = datasets["geolocation"]

    # Geolocation contains multiple observations per ZIP prefix, so
    # uniqueness of the ZIP prefix itself is NOT expected.
    geolocation_zip_values = (
        geolocation["geolocation_zip_code_prefix"]
        .dropna()
        .drop_duplicates()
    )

    logger.info(
        "Geolocation reference contains %s unique ZIP prefixes.",
        f"{len(geolocation_zip_values):,}",
    )

    # Customers
    if "customer_zip_code_prefix" in datasets["customers"].columns:
        validate_optional_foreign_key(
            child_name="customers",
            child_df=datasets["customers"],
            child_column="customer_zip_code_prefix",
            parent_name="geolocation",
            parent_df=geolocation,
            parent_column="geolocation_zip_code_prefix",
        )
    else:
        raise CrossTableValidationError(
            "customers.csv does not contain "
            "'customer_zip_code_prefix'."
        )

    # Sellers
    if "seller_zip_code_prefix" in datasets["sellers"].columns:
        validate_optional_foreign_key(
            child_name="sellers",
            child_df=datasets["sellers"],
            child_column="seller_zip_code_prefix",
            parent_name="geolocation",
            parent_df=geolocation,
            parent_column="geolocation_zip_code_prefix",
        )
    else:
        raise CrossTableValidationError(
            "sellers.csv does not contain "
            "'seller_zip_code_prefix'."
        )

    logger.info(
        "Geographic referential-integrity validation completed."
    )


# ---------------------------------------------------------------------------
# Relationship profiling
# ---------------------------------------------------------------------------


def profile_relationships(
    datasets: dict[str, pd.DataFrame],
) -> None:
    """Generate useful cross-table relationship statistics."""

    orders = datasets["orders"]
    order_items = datasets["order_items"]
    payments = datasets["payments"]
    reviews = datasets["reviews"]

    logger.info("Starting cross-table relationship profiling.")

    # Orders with order items
    orders_with_items = order_items["order_id"].nunique()

    logger.info(
        "Orders represented in order_items: %s of %s.",
        f"{orders_with_items:,}",
        f"{orders['order_id'].nunique():,}",
    )

    # Orders with payments
    orders_with_payments = payments["order_id"].nunique()

    logger.info(
        "Orders represented in payments: %s of %s.",
        f"{orders_with_payments:,}",
        f"{orders['order_id'].nunique():,}",
    )

    # Orders with reviews
    orders_with_reviews = reviews["order_id"].nunique()

    logger.info(
        "Orders represented in reviews: %s of %s.",
        f"{orders_with_reviews:,}",
        f"{orders['order_id'].nunique():,}",
    )

    # Items per order
    items_per_order = order_items.groupby("order_id").size()

    logger.info(
        "Maximum order items for one order: %s",
        f"{items_per_order.max():,}",
    )

    logger.info(
        "Average order items per order with items: %.2f",
        items_per_order.mean(),
    )

    # Payments per order
    payments_per_order = payments.groupby("order_id").size()

    logger.info(
        "Maximum payments for one order: %s",
        f"{payments_per_order.max():,}",
    )

    logger.info(
        "Average payments per order with payments: %.2f",
        payments_per_order.mean(),
    )

    # Reviews per order
    reviews_per_order = reviews.groupby("order_id").size()

    logger.info(
        "Maximum reviews for one order: %s",
        f"{reviews_per_order.max():,}",
    )

    logger.info(
        "Orders with multiple reviews: %s",
        f"{(reviews_per_order > 1).sum():,}",
    )

    logger.info(
        "Cross-table relationship profiling completed."
    )


# ---------------------------------------------------------------------------
# Main validation workflow
# ---------------------------------------------------------------------------


def main() -> None:
    """Execute the complete cross-table validation pipeline."""

    logger.info(
        "============================================================"
    )
    logger.info(
        "Starting Olist cross-table integrity validation."
    )
    logger.info(
        "============================================================"
    )

    try:
        # --------------------------------------------------------------
        # Load datasets
        # --------------------------------------------------------------

        datasets = {
            name: load_dataset(name, path)
            for name, path in FILES.items()
        }

        # --------------------------------------------------------------
        # Required schema
        # --------------------------------------------------------------

        validate_required_columns(
            "customers",
            datasets["customers"],
            [
                "customer_id",
                "customer_zip_code_prefix",
            ],
        )

        validate_required_columns(
            "orders",
            datasets["orders"],
            [
                "order_id",
                "customer_id",
            ],
        )

        validate_required_columns(
            "order_items",
            datasets["order_items"],
            [
                "order_id",
                "order_item_id",
                "product_id",
                "seller_id",
            ],
        )

        validate_required_columns(
            "products",
            datasets["products"],
            ["product_id"],
        )

        validate_required_columns(
            "payments",
            datasets["payments"],
            [
                "order_id",
                "payment_sequential",
            ],
        )

        validate_required_columns(
            "sellers",
            datasets["sellers"],
            [
                "seller_id",
                "seller_zip_code_prefix",
            ],
        )

        validate_required_columns(
            "reviews",
            datasets["reviews"],
            [
                "review_id",
                "order_id",
            ],
        )

        validate_required_columns(
            "geolocation",
            datasets["geolocation"],
            [
                "geolocation_zip_code_prefix",
            ],
        )

        # --------------------------------------------------------------
        # Row counts
        # --------------------------------------------------------------

        logger.info("Starting dataset row-count validation.")

        for name, df in datasets.items():
            validate_row_count(name, df)

        # --------------------------------------------------------------
        # Dataset-level keys
        # --------------------------------------------------------------

        validate_dataset_keys(datasets)

        # --------------------------------------------------------------
        # Key NULL validation
        # --------------------------------------------------------------

        validate_key_nulls(datasets)

        # --------------------------------------------------------------
        # Critical referential integrity
        # --------------------------------------------------------------

        validate_referential_integrity(datasets)

        # --------------------------------------------------------------
        # Geographic relationships
        # --------------------------------------------------------------

        validate_geographic_references(datasets)

        # --------------------------------------------------------------
        # Relationship profiling
        # --------------------------------------------------------------

        profile_relationships(datasets)

        # --------------------------------------------------------------
        # Success
        # --------------------------------------------------------------

        logger.info(
            "============================================================"
        )
        logger.info(
            "Cross-table integrity validation completed successfully."
        )
        logger.info(
            "All critical referential-integrity checks passed."
        )
        logger.info(
            "============================================================"
        )

    except CrossTableValidationError as exc:
        logger.error(
            "Cross-table integrity validation FAILED: %s",
            exc,
        )
        sys.exit(1)

    except Exception:
        logger.exception(
            "Unexpected error during cross-table validation."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()