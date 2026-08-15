"""
Cross-table integrity validation for the Olist source-system simulator.

Validates referential integrity and business relationships across the
transformed datasets.

Tables:
    customers
    orders
    order_items
    products
    payments
    sellers
    reviews
    geolocation
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

from cross_table_util.cross_table_config import LOG_FORMAT
from cross_table_util.cross_table_io import load_all_tables
from cross_table_util.cross_table_validation import (
    normalize_zip_codes,
    validate_customer_zip_coverage,
    validate_foreign_key,
    validate_required_columns,
    validate_unique_key,
)

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
)

logger = logging.getLogger(__name__)


# Utility functions
def load_table(path: Path, table_name: str) -> pd.DataFrame:
    """Load a transformed CSV table."""
    return load_all_tables()[table_name]


def validate_required_columns(
    dataframe: pd.DataFrame,
    required_columns: list[str],
    table_name: str,
) -> None:
    """Validate required columns."""
    _validate_required_columns = __import__(
        "cross_table_util.cross_table_validation",
        fromlist=["validate_required_columns"],
    ).validate_required_columns

    _validate_required_columns(
        dataframe,
        required_columns,
        table_name,
    )


def validate_unique_key(
    dataframe: pd.DataFrame,
    columns: list[str],
    table_name: str,
) -> None:
    """Validate uniqueness of a single or composite key."""
    _validate_unique_key = __import__(
        "cross_table_util.cross_table_validation",
        fromlist=["validate_unique_key"],
    ).validate_unique_key

    _validate_unique_key(
        dataframe,
        columns,
        table_name,
    )

def validate_foreign_key(
    child: pd.DataFrame,
    child_column: str,
    parent: pd.DataFrame,
    parent_column: str,
    relationship_name: str,
) -> None:
    """Validate child-to-parent relationship."""
    _validate_foreign_key = __import__(
        "cross_table_util.cross_table_validation",
        fromlist=["validate_foreign_key"],
    ).validate_foreign_key

    _validate_foreign_key(
        child,
        child_column,
        parent,
        parent_column,
        relationship_name,
    )


def normalize_zip_codes(series: pd.Series) -> pd.Series:
    """Normalize ZIP-code prefixes."""
    return __import__(
        "cross_table_util.cross_table_validation",
        fromlist=["normalize_zip_codes"],
    ).normalize_zip_codes(series)


# Main validation
def main() -> None:
    logger.info("=" * 60)
    logger.info(
        "Starting Olist cross-table integrity validation."
    )
    logger.info("=" * 60)

    tables = load_all_tables()

    customers = tables["customers"]
    orders = tables["orders"]
    order_items = tables["order_items"]
    products = tables["products"]
    payments = tables["payments"]
    sellers = tables["sellers"]
    reviews = tables["reviews"]
    geolocation = tables["geolocation"]

    # Schema validation
    validate_required_columns(
        customers,
        [
            "customer_id",
            "customer_unique_id",
            "zip_code_prefix",
            "signup_date",
        ],
        "customers",
    )

    validate_required_columns(
        orders,
        [
            "order_id",
            "customer_id",
            "order_purchase_timestamp",
        ],
        "orders",
    )

    validate_required_columns(
        order_items,
        [
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
        ],
        "order_items",
    )

    validate_required_columns(
        products,
        [
            "product_id",
        ],
        "products",
    )

    validate_required_columns(
        payments,
        [
            "order_id",
            "payment_sequential",
        ],
        "payments",
    )

    validate_required_columns(
        sellers,
        [
            "seller_id",
        ],
        "sellers",
    )

    validate_required_columns(
        reviews,
        [
            "review_id",
            "order_id",
            "review_score",
        ],
        "reviews",
    )

    validate_required_columns(
        geolocation,
        [
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
        ],
        "geolocation",
    )

    logger.info("All table schema validations passed.")

    # Primary / composite key validation
    validate_unique_key(
        customers,
        ["customer_id"],
        "customers",
    )

    validate_unique_key(
        orders,
        ["order_id"],
        "orders",
    )

    validate_unique_key(
        order_items,
        ["order_id", "order_item_id"],
        "order_items",
    )

    validate_unique_key(
        products,
        ["product_id"],
        "products",
    )

    validate_unique_key(
        payments,
        ["order_id", "payment_sequential"],
        "payments",
    )

    validate_unique_key(
        sellers,
        ["seller_id"],
        "sellers",
    )

    validate_unique_key(
        reviews,
        ["review_id", "order_id"],
        "reviews",
    )

    logger.info(
        "Review uniqueness model validated: "
        "review_id alone is non-unique; "
        "review_id + order_id is unique."
    )

    # Foreign-key validation
    validate_foreign_key(
        orders,
        "customer_id",
        customers,
        "customer_id",
        "Orders → Customers",
    )

    validate_foreign_key(
        order_items,
        "order_id",
        orders,
        "order_id",
        "Order Items → Orders",
    )

    validate_foreign_key(
        order_items,
        "product_id",
        products,
        "product_id",
        "Order Items → Products",
    )

    validate_foreign_key(
        order_items,
        "seller_id",
        sellers,
        "seller_id",
        "Order Items → Sellers",
    )

    validate_foreign_key(
        payments,
        "order_id",
        orders,
        "order_id",
        "Payments → Orders",
    )

    validate_foreign_key(
        reviews,
        "order_id",
        orders,
        "order_id",
        "Reviews → Orders",
    )

    # Customer → geolocation ZIP validation
    customer_zip_coverage = validate_customer_zip_coverage(
        customers,
        geolocation,
    )

    # Order purchase timestamp validation
    logger.info(
        "Starting order purchase timestamp validation."
    )

    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"],
        errors="coerce",
    )

    invalid_purchase_timestamps = (
        orders["order_purchase_timestamp"].isna().sum()
    )

    if invalid_purchase_timestamps > 0:
        raise ValueError(
            "Orders contain "
            f"{invalid_purchase_timestamps:,} invalid or NULL "
            "order_purchase_timestamp values."
        )

    logger.info(
        "Order purchase timestamp validation passed."
    )

    # Customer signup_date validation
    logger.info(
        "Starting customer signup_date temporal validation."
    )

    customers["signup_date"] = pd.to_datetime(
        customers["signup_date"],
        errors="coerce",
    )

    null_signup_dates = customers["signup_date"].isna().sum()

    if null_signup_dates > 0:
        raise ValueError(
            "Customers contain "
            f"{null_signup_dates:,} NULL or invalid signup_date values."
        )

    logger.info(
        "Customer signup_date parsing validation passed."
    )

    expected_signup_dates = (
        orders
        .groupby("customer_id")["order_purchase_timestamp"]
        .min()
        .rename("expected_signup_date")
    )

    customer_signup_validation = customers[
        ["customer_id", "signup_date"]
    ].merge(
        expected_signup_dates,
        left_on="customer_id",
        right_index=True,
        how="left",
        validate="one_to_one",
    )

    customers_without_orders = (
        customer_signup_validation["expected_signup_date"].isna()
    ).sum()

    customers_with_orders = (
        ~customer_signup_validation["expected_signup_date"].isna()
    ).sum()

    logger.info(
        "Customers without orders: %s",
        f"{customers_without_orders:,}",
    )

    logger.info(
        "Customers with orders: %s",
        f"{customers_with_orders:,}",
    )

    customers_with_orders_mask = (
        customer_signup_validation["expected_signup_date"].notna()
    )

    signup_mismatches = (
        customer_signup_validation.loc[
            customers_with_orders_mask,
            "signup_date",
        ]
        != customer_signup_validation.loc[
            customers_with_orders_mask,
            "expected_signup_date",
        ]
    ).sum()

    if signup_mismatches > 0:
        raise ValueError(
            "Customer signup_date validation failed: "
            f"{signup_mismatches:,} customers have a signup_date "
            "different from their earliest order purchase timestamp."
        )

    logger.info(
        "Customer signup_date derivation validation passed."
    )

    temporal_validation = orders[
        ["customer_id", "order_purchase_timestamp"]
    ].merge(
        customers[["customer_id", "signup_date"]],
        on="customer_id",
        how="left",
        validate="many_to_one",
    )

    invalid_temporal_records = (
        temporal_validation["signup_date"]
        > temporal_validation["order_purchase_timestamp"]
    ).sum()

    if invalid_temporal_records > 0:
        raise ValueError(
            "Customer temporal integrity validation failed: "
            f"{invalid_temporal_records:,} orders have a purchase "
            "timestamp earlier than the customer's signup_date."
        )

    logger.info(
        "Customer temporal integrity validation passed."
    )

    # Geolocation structural validation
    logger.info(
        "Starting geolocation structural validation."
    )

    geolocation_lat = pd.to_numeric(
        geolocation["geolocation_lat"],
        errors="coerce",
    )

    geolocation_lng = pd.to_numeric(
        geolocation["geolocation_lng"],
        errors="coerce",
    )

    invalid_latitude = (
        geolocation_lat.isna()
        | ~geolocation_lat.between(-90, 90)
    ).sum()

    invalid_longitude = (
        geolocation_lng.isna()
        | ~geolocation_lng.between(-180, 180)
    ).sum()

    if invalid_latitude > 0:
        raise ValueError(
            f"Geolocation contains {invalid_latitude:,} "
            "invalid latitude values."
        )

    if invalid_longitude > 0:
        raise ValueError(
            f"Geolocation contains {invalid_longitude:,} "
            "invalid longitude values."
        )

    logger.info(
        "Geolocation coordinate validation passed."
    )

    # Summary statistics
    logger.info("=" * 60)
    logger.info(
        "Cross-table integrity validation completed successfully."
    )
    logger.info("=" * 60)

    logger.info(
        "Customers: %s",
        f"{len(customers):,}",
    )

    logger.info(
        "Orders: %s",
        f"{len(orders):,}",
    )

    logger.info(
        "Order items: %s",
        f"{len(order_items):,}",
    )

    logger.info(
        "Products: %s",
        f"{len(products):,}",
    )

    logger.info(
        "Payments: %s",
        f"{len(payments):,}",
    )

    logger.info(
        "Sellers: %s",
        f"{len(sellers):,}",
    )

    logger.info(
        "Reviews: %s",
        f"{len(reviews):,}",
    )

    logger.info(
        "Geolocation records: %s",
        f"{len(geolocation):,}",
    )

    logger.info(
        "Customer ZIP coverage: %.2f%%",
        customer_zip_coverage,
    )

    logger.info(
        "Customers with orders: %s",
        f"{customers_with_orders:,}",
    )

    logger.info(
        "Customers without orders: %s",
        f"{customers_without_orders:,}",
    )

    logger.info(
        "All referential integrity validations passed."
    )

    logger.info(
        "All temporal integrity validations passed."
    )

    logger.info(
        "All structural integrity validations passed."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.exception(
            "Cross-table integrity validation FAILED: %s",
            exc,
        )
        sys.exit(1)