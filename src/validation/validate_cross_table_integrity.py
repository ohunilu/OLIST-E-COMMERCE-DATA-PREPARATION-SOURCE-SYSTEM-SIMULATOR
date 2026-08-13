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

Key relationships:

    customers.customer_id
        -> orders.customer_id

    orders.order_id
        -> order_items.order_id

    products.product_id
        -> order_items.product_id

    sellers.seller_id
        -> order_items.seller_id

    orders.order_id
        -> payments.order_id

    orders.order_id
        -> reviews.order_id

    customers.zip_code_prefix
        -> geolocation.geolocation_zip_code_prefix

Temporal business rule:

    customers.signup_date
        =
    MIN(orders.order_purchase_timestamp)

for every customer with at least one order.
"""

from pathlib import Path
import logging
import sys

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path("/app")
DATA_DIR = BASE_DIR / "simulated_data"

CUSTOMERS_FILE = DATA_DIR / "customers.csv"
ORDERS_FILE = DATA_DIR / "orders.csv"
ORDER_ITEMS_FILE = DATA_DIR / "order_items.csv"
PRODUCTS_FILE = DATA_DIR / "products.csv"
PAYMENTS_FILE = DATA_DIR / "payments.csv"
SELLERS_FILE = DATA_DIR / "sellers.csv"
REVIEWS_FILE = DATA_DIR / "reviews.csv"
GEOLOCATION_FILE = DATA_DIR / "geolocation.csv"

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def load_table(
    path: Path,
    table_name: str,
) -> pd.DataFrame:
    """Load a transformed CSV table."""
    logger.info("Reading %s: %s", table_name, path)

    if not path.exists():
        raise FileNotFoundError(
            f"Required table does not exist: {path}"
        )

    dataframe = pd.read_csv(path)

    logger.info(
        "%s records loaded: %s",
        table_name.capitalize(),
        f"{len(dataframe):,}",
    )

    return dataframe


def validate_required_columns(
    dataframe: pd.DataFrame,
    required_columns: list[str],
    table_name: str,
) -> None:
    """Validate required columns."""
    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"{table_name} is missing required columns: "
            f"{missing_columns}"
        )


def validate_unique_key(
    dataframe: pd.DataFrame,
    columns: list[str],
    table_name: str,
) -> None:
    """Validate uniqueness of a single or composite key."""
    duplicate_count = dataframe.duplicated(columns).sum()

    if duplicate_count > 0:
        raise ValueError(
            f"{table_name} contains {duplicate_count:,} "
            f"duplicate records for key {columns}."
        )


def validate_foreign_key(
    child: pd.DataFrame,
    child_column: str,
    parent: pd.DataFrame,
    parent_column: str,
    relationship_name: str,
) -> None:
    """
    Validate that every non-null child foreign key exists in the parent.
    """
    child_values = set(
        child[child_column].dropna()
    )

    parent_values = set(
        parent[parent_column].dropna()
    )

    missing_values = child_values - parent_values

    if missing_values:
        sample = list(missing_values)[:10]

        raise ValueError(
            f"{relationship_name} validation failed: "
            f"{len(missing_values):,} child values do not exist "
            f"in the parent table. Sample: {sample}"
        )

    logger.info(
        "%s validation passed.",
        relationship_name,
    )


def normalize_zip_codes(series: pd.Series) -> pd.Series:
    """
    Normalize ZIP-code prefixes to five-character strings.

    The Olist data represents Brazilian ZIP prefixes as integers, which can
    remove leading zeroes. Normalization ensures reliable comparison.
    """
    return (
        series
        .dropna()
        .astype(int)
        .astype(str)
        .str.zfill(5)
    )


# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------

def main() -> None:

    logger.info("=" * 60)
    logger.info(
        "Starting Olist cross-table integrity validation."
    )
    logger.info("=" * 60)

    # -----------------------------------------------------------------------
    # Load tables
    # -----------------------------------------------------------------------

    customers = load_table(
        CUSTOMERS_FILE,
        "customers",
    )

    orders = load_table(
        ORDERS_FILE,
        "orders",
    )

    order_items = load_table(
        ORDER_ITEMS_FILE,
        "order_items",
    )

    products = load_table(
        PRODUCTS_FILE,
        "products",
    )

    payments = load_table(
        PAYMENTS_FILE,
        "payments",
    )

    sellers = load_table(
        SELLERS_FILE,
        "sellers",
    )

    reviews = load_table(
        REVIEWS_FILE,
        "reviews",
    )

    geolocation = load_table(
        GEOLOCATION_FILE,
        "geolocation",
    )

    # -----------------------------------------------------------------------
    # Schema validation
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # Primary / composite key validation
    # -----------------------------------------------------------------------

    validate_unique_key(
        customers,
        ["customer_id"],
        "customers",
    )

    logger.info("Customer primary key validation passed.")

    validate_unique_key(
        orders,
        ["order_id"],
        "orders",
    )

    logger.info("Order primary key validation passed.")

    validate_unique_key(
        order_items,
        ["order_id", "order_item_id"],
        "order_items",
    )

    logger.info(
        "Order-item composite key validation passed."
    )

    validate_unique_key(
        products,
        ["product_id"],
        "products",
    )

    logger.info("Product primary key validation passed.")

    validate_unique_key(
        payments,
        ["order_id", "payment_sequential"],
        "payments",
    )

    logger.info(
        "Payment composite key validation passed."
    )

    validate_unique_key(
        sellers,
        ["seller_id"],
        "sellers",
    )

    logger.info("Seller primary key validation passed.")

    # -----------------------------------------------------------------------
    # Review key validation
    # -----------------------------------------------------------------------

    # review_id is intentionally NOT required to be unique.
    #
    # The source data contains duplicate review_id values, but the
    # review_id + order_id combination is unique.

    validate_unique_key(
        reviews,
        ["review_id", "order_id"],
        "reviews",
    )

    logger.info(
        "Review composite key validation passed."
    )

    logger.info(
        "Review uniqueness model validated: "
        "review_id alone is non-unique; "
        "review_id + order_id is unique."
    )

    # -----------------------------------------------------------------------
    # Foreign-key validation
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # Customer → Geolocation ZIP validation
    # -----------------------------------------------------------------------

    logger.info(
        "Starting customer → geolocation ZIP coverage validation."
    )

    customer_zips = set(
        normalize_zip_codes(
            customers["zip_code_prefix"]
        )
    )

    geolocation_zips = set(
        normalize_zip_codes(
            geolocation["geolocation_zip_code_prefix"]
        )
    )

    missing_customer_zips = customer_zips - geolocation_zips

    matched_customer_zips = (
        customer_zips & geolocation_zips
    )

    if missing_customer_zips:

        logger.warning(
            "Customer ZIP coverage is incomplete."
        )

        logger.warning(
            "Customer ZIP prefixes: %s",
            f"{len(customer_zips):,}",
        )

        logger.warning(
            "ZIP prefixes found in geolocation: %s",
            f"{len(matched_customer_zips):,}",
        )

        logger.warning(
            "ZIP prefixes without geolocation mapping: %s",
            f"{len(missing_customer_zips):,}",
        )

        logger.warning(
            "Sample missing ZIP prefixes: %s",
            sorted(missing_customer_zips)[:20],
        )

    else:

        logger.info(
            "Customer → geolocation ZIP coverage validation passed."
        )

    customer_zip_coverage = (
        len(matched_customer_zips)
        / len(customer_zips)
        * 100
        if customer_zips
        else 100.0
    )

    logger.info(
        "Customer ZIP coverage: %.2f%%",
        customer_zip_coverage,
    )

    # -----------------------------------------------------------------------
    # Order purchase timestamp validation
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # Customer signup_date validation
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # Derive expected signup dates from orders
    # -----------------------------------------------------------------------

    expected_signup_dates = (
        orders
        .groupby("customer_id")["order_purchase_timestamp"]
        .min()
        .rename("expected_signup_date")
    )

    customer_signup_validation = customers[
        [
            "customer_id",
            "signup_date",
        ]
    ].merge(
        expected_signup_dates,
        left_on="customer_id",
        right_index=True,
        how="left",
        validate="one_to_one",
    )

    # -----------------------------------------------------------------------
    # Customers without orders
    # -----------------------------------------------------------------------

    customers_without_orders = (
        customer_signup_validation["expected_signup_date"]
        .isna()
    ).sum()

    logger.info(
        "Customers without orders: %s",
        f"{customers_without_orders:,}",
    )

    customers_with_orders = (
        ~customer_signup_validation["expected_signup_date"].isna()
    ).sum()

    logger.info(
        "Customers with orders: %s",
        f"{customers_with_orders:,}",
    )

    # -----------------------------------------------------------------------
    # Signup date equality validation
    # -----------------------------------------------------------------------

    customers_with_orders_mask = (
        customer_signup_validation["expected_signup_date"]
        .notna()
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

        mismatch_sample = (
            customer_signup_validation.loc[
                customers_with_orders_mask
                & (
                    customer_signup_validation["signup_date"]
                    != customer_signup_validation[
                        "expected_signup_date"
                    ]
                )
            ]
            .head(10)
            .to_dict("records")
        )

        raise ValueError(
            "Customer signup_date validation failed: "
            f"{signup_mismatches:,} customers have a signup_date "
            "different from their earliest order purchase timestamp. "
            f"Sample: {mismatch_sample}"
        )

    logger.info(
        "Customer signup_date derivation validation passed."
    )

    logger.info(
        "signup_date equals MIN(order_purchase_timestamp) "
        "for all customers with orders."
    )

    # -----------------------------------------------------------------------
    # Temporal ordering validation
    # -----------------------------------------------------------------------

    logger.info(
        "Validating signup_date <= every customer purchase timestamp."
    )

    temporal_validation = orders[
        [
            "customer_id",
            "order_purchase_timestamp",
        ]
    ].merge(
        customers[
            [
                "customer_id",
                "signup_date",
            ]
        ],
        on="customer_id",
        how="left",
        validate="many_to_one",
    )

    invalid_temporal_records = (
        temporal_validation["signup_date"]
        > temporal_validation["order_purchase_timestamp"]
    ).sum()

    if invalid_temporal_records > 0:

        sample = (
            temporal_validation.loc[
                temporal_validation["signup_date"]
                > temporal_validation[
                    "order_purchase_timestamp"
                ]
            ]
            .head(10)
            .to_dict("records")
        )

        raise ValueError(
            "Customer temporal integrity validation failed: "
            f"{invalid_temporal_records:,} orders have a purchase "
            "timestamp earlier than the customer's signup_date. "
            f"Sample: {sample}"
        )

    logger.info(
        "Customer temporal integrity validation passed."
    )

    logger.info(
        "All customer signup dates occur on or before "
        "their corresponding order purchase timestamps."
    )

    # -----------------------------------------------------------------------
    # Geolocation structural validation
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # Summary statistics
    # -----------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    try:
        main()

    except Exception as exc:

        logger.exception(
            "Cross-table integrity validation FAILED: %s",
            exc,
        )

        sys.exit(1)