"""
Enrich customer signup dates from transformed order purchase timestamps.

The Olist source customer dataset does not contain a reliable customer
creation timestamp. For the simulator, signup_date is therefore derived
from the earliest recorded order_purchase_timestamp for each customer.

Input:
    /app/simulated_data/customers.csv
    /app/simulated_data/orders.csv

Output:
    /app/simulated_data/customers.csv
"""

from pathlib import Path
import logging
import sys

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path("/app")

CUSTOMERS_FILE = BASE_DIR / "simulated_data" / "customers.csv"
ORDERS_FILE = BASE_DIR / "simulated_data" / "orders.csv"

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
# Validation helpers
# ---------------------------------------------------------------------------

def validate_required_columns(
    dataframe: pd.DataFrame,
    required_columns: list[str],
    table_name: str,
) -> None:
    """
    Validate that all required columns exist.
    """
    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"{table_name} is missing required columns: {missing_columns}"
        )


def validate_unique_key(
    dataframe: pd.DataFrame,
    column: str,
    table_name: str,
) -> None:
    """
    Validate that a column contains no duplicate values.
    """
    duplicate_count = dataframe[column].duplicated().sum()

    if duplicate_count > 0:
        raise ValueError(
            f"{table_name}.{column} contains "
            f"{duplicate_count:,} duplicate values."
        )


# ---------------------------------------------------------------------------
# Main transformation
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=" * 60)
    logger.info("Starting customer signup date enrichment.")
    logger.info("=" * 60)

    # -----------------------------------------------------------------------
    # Read customers
    # -----------------------------------------------------------------------

    logger.info("Reading customers: %s", CUSTOMERS_FILE)

    customers = pd.read_csv(CUSTOMERS_FILE)

    logger.info(
        "Customer records loaded: %s",
        f"{len(customers):,}",
    )

    # -----------------------------------------------------------------------
    # Read orders
    # -----------------------------------------------------------------------

    logger.info("Reading transformed orders reference: %s", ORDERS_FILE)

    orders = pd.read_csv(ORDERS_FILE)

    logger.info(
        "Order records loaded: %s",
        f"{len(orders):,}",
    )

    # -----------------------------------------------------------------------
    # Schema validation
    # -----------------------------------------------------------------------

    validate_required_columns(
        customers,
        [
            "customer_id",
            "customer_unique_id",
            "signup_date",
        ],
        "customers",
    )

    logger.info("Customer schema validation passed.")

    validate_required_columns(
        orders,
        [
            "order_id",
            "customer_id",
            "order_purchase_timestamp",
        ],
        "orders",
    )

    logger.info("Orders reference schema validation passed.")

    # -----------------------------------------------------------------------
    # Key validation
    # -----------------------------------------------------------------------

    validate_unique_key(
        customers,
        "customer_id",
        "customers",
    )

    logger.info("Customer key validation passed.")

    if orders["order_id"].duplicated().any():
        duplicate_orders = orders["order_id"].duplicated().sum()

        raise ValueError(
            f"orders.order_id contains "
            f"{duplicate_orders:,} duplicate values."
        )

    logger.info("Order key validation passed.")

    # -----------------------------------------------------------------------
    # Parse order purchase timestamps
    # -----------------------------------------------------------------------

    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"],
        errors="coerce",
    )

    invalid_order_timestamps = (
        orders["order_purchase_timestamp"].isna().sum()
    )

    if invalid_order_timestamps > 0:
        raise ValueError(
            "Orders contain "
            f"{invalid_order_timestamps:,} invalid or NULL "
            "order_purchase_timestamp values."
        )

    logger.info("Order purchase timestamp parsing passed.")

    # -----------------------------------------------------------------------
    # Validate customer references
    # -----------------------------------------------------------------------

    customer_ids = set(customers["customer_id"])

    order_customer_ids = set(
        orders["customer_id"].dropna()
    )

    unknown_customer_ids = order_customer_ids - customer_ids

    if unknown_customer_ids:
        logger.error(
            "Orders contain %s customer_id values that do not exist "
            "in customers.",
            f"{len(unknown_customer_ids):,}",
        )

        sample = list(unknown_customer_ids)[:10]

        raise ValueError(
            "Order-to-customer referential integrity validation failed. "
            f"Sample unknown customer IDs: {sample}"
        )

    logger.info("Order-to-customer reference validation passed.")

    # -----------------------------------------------------------------------
    # Derive earliest purchase timestamp per customer
    # -----------------------------------------------------------------------

    logger.info(
        "Deriving signup_date from earliest "
        "order_purchase_timestamp per customer."
    )

    signup_dates = (
        orders
        .groupby("customer_id", as_index=False)[
            "order_purchase_timestamp"
        ]
        .min()
        .rename(
            columns={
                "order_purchase_timestamp": "signup_date"
            }
        )
    )

    logger.info(
        "Signup dates derived for %s customers.",
        f"{len(signup_dates):,}",
    )

    # -----------------------------------------------------------------------
    # Validate derived signup dates
    # -----------------------------------------------------------------------

    if signup_dates["signup_date"].isna().any():
        null_signup_dates = signup_dates["signup_date"].isna().sum()

        raise ValueError(
            f"{null_signup_dates:,} derived signup dates are NULL."
        )

    logger.info("Derived signup date NULL validation passed.")

    # -----------------------------------------------------------------------
    # Preserve original customer row count
    # -----------------------------------------------------------------------

    original_customer_count = len(customers)

    # Remove the existing placeholder values before enrichment.
    customers = customers.drop(columns=["signup_date"])

    customers = customers.merge(
        signup_dates,
        on="customer_id",
        how="left",
        validate="one_to_one",
    )

    # -----------------------------------------------------------------------
    # Row-count validation
    # -----------------------------------------------------------------------

    if len(customers) != original_customer_count:
        raise ValueError(
            "Customer row count changed during signup date enrichment. "
            f"Expected {original_customer_count:,}, "
            f"got {len(customers):,}."
        )

    logger.info(
        "Customer row-count validation passed: %s records.",
        f"{len(customers):,}",
    )

    # -----------------------------------------------------------------------
    # Signup date coverage validation
    # -----------------------------------------------------------------------

    customers_with_orders = customers["customer_id"].isin(
        signup_dates["customer_id"]
    )

    missing_signup_dates = (
        customers.loc[
            customers_with_orders,
            "signup_date"
        ].isna().sum()
    )

    if missing_signup_dates > 0:
        raise ValueError(
            f"{missing_signup_dates:,} customers with orders "
            "have NULL signup_date values."
        )

    customers_without_orders = (~customers_with_orders).sum()

    logger.info(
        "Customers with orders: %s",
        f"{customers_with_orders.sum():,}",
    )

    logger.info(
        "Customers without orders: %s",
        f"{customers_without_orders:,}",
    )

    logger.info(
        "Customers with orders and valid signup_date: %s",
        f"{customers_with_orders.sum():,}",
    )

    # -----------------------------------------------------------------------
    # Temporal integrity validation
    # -----------------------------------------------------------------------

    logger.info(
        "Validating signup_date against customer purchase history."
    )

    validation_frame = orders[
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

    invalid_temporal_relationships = (
        validation_frame["signup_date"]
        > validation_frame["order_purchase_timestamp"]
    ).sum()

    if invalid_temporal_relationships > 0:
        raise ValueError(
            "Temporal integrity validation failed: "
            f"{invalid_temporal_relationships:,} orders have a "
            "purchase timestamp earlier than customer signup_date."
        )

    logger.info(
        "Temporal integrity validation passed: "
        "signup_date <= order_purchase_timestamp."
    )

    # -----------------------------------------------------------------------
    # Validate signup date equals earliest purchase
    # -----------------------------------------------------------------------

    expected_signup_dates = (
        orders
        .groupby("customer_id")["order_purchase_timestamp"]
        .min()
        .rename("expected_signup_date")
    )

    comparison = customers[
        [
            "customer_id",
            "signup_date",
        ]
    ].merge(
        expected_signup_dates,
        left_on="customer_id",
        right_index=True,
        how="inner",
        validate="one_to_one",
    )

    mismatched_signup_dates = (
        comparison["signup_date"]
        != comparison["expected_signup_date"]
    ).sum()

    if mismatched_signup_dates > 0:
        raise ValueError(
            "Signup date derivation validation failed: "
            f"{mismatched_signup_dates:,} customers have a signup_date "
            "different from their earliest purchase timestamp."
        )

    logger.info(
        "Signup date derivation validation passed: "
        "signup_date equals earliest purchase timestamp."
    )

    # -----------------------------------------------------------------------
    # Final key validation
    # -----------------------------------------------------------------------

    validate_unique_key(
        customers,
        "customer_id",
        "customers",
    )

    logger.info("Output customer key validation passed.")

    # -----------------------------------------------------------------------
    # Final schema validation
    # -----------------------------------------------------------------------

    expected_columns = [
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

    if list(customers.columns) != expected_columns:
        raise ValueError(
            "Output customer schema validation failed.\n"
            f"Expected: {expected_columns}\n"
            f"Actual:   {customers.columns.tolist()}"
        )

    logger.info("Output customer schema validation passed.")

    # -----------------------------------------------------------------------
    # Write output
    # -----------------------------------------------------------------------

    customers["signup_date"] = customers["signup_date"].dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    customers.to_csv(
        CUSTOMERS_FILE,
        index=False,
    )

    logger.info(
        "Output file written: %s",
        CUSTOMERS_FILE,
    )

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------

    logger.info("=" * 60)
    logger.info("Customer signup date enrichment completed successfully.")
    logger.info("Customer records: %s", f"{len(customers):,}")
    logger.info(
        "Customers with orders: %s",
        f"{customers_with_orders.sum():,}",
    )
    logger.info(
        "Customers without orders: %s",
        f"{customers_without_orders:,}",
    )

    signup_min = pd.to_datetime(customers["signup_date"]).min()
    signup_max = pd.to_datetime(customers["signup_date"]).max()

    logger.info(
        "Signup date range: %s to %s",
        signup_min,
        signup_max,
    )

    logger.info("Output file: %s", CUSTOMERS_FILE)
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.exception(
            "Customer signup date enrichment FAILED: %s",
            exc,
        )
        sys.exit(1)