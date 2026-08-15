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

from __future__ import annotations

import logging
import sys

from customer_signup_util.customer_signup_config import (
    CUSTOMERS_FILE,
    ORDERS_FILE,
    LOG_FORMAT,
)
from customer_signup_util.customer_signup_io import (
    read_customers as _read_customers,
    read_orders as _read_orders,
    write_customers as _write_customers,
)
from customer_signup_util.customer_signup_transform import (
    enrich_customer_signup_dates as _enrich_customer_signup_dates,
)
from customer_signup_util.customer_signup_validation import (
    validate_required_columns as _validate_required_columns,
    validate_unique_key as _validate_unique_key,
)

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
)

logger = logging.getLogger(__name__)

# Validation helpers
def validate_required_columns(
    dataframe,
    required_columns,
    table_name,
):
    _validate_required_columns(
        dataframe,
        required_columns,
        table_name,
    )


def validate_unique_key(
    dataframe,
    column,
    table_name,
):
    _validate_unique_key(
        dataframe,
        column,
        table_name,
    )


# Main transformation
def main() -> None:
    logger.info("=" * 60)
    logger.info("Starting customer signup date enrichment.")
    logger.info("=" * 60)

    customers = _read_customers()
    orders = _read_orders()

    validate_required_columns(
        customers,
        [
            "customer_id",
            "customer_unique_id",
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

    validate_unique_key(
        customers,
        "customer_id",
        "customers",
    )

    if orders["order_id"].duplicated().any():
        duplicate_orders = orders["order_id"].duplicated().sum()
        raise ValueError(
            f"orders.order_id contains "
            f"{duplicate_orders:,} duplicate values."
        )

    logger.info("Order key validation passed.")

    customers = _enrich_customer_signup_dates(
        customers,
        orders,
    )

    _write_customers(customers)

    logger.info("=" * 60)
    logger.info("Customer signup date enrichment completed successfully.")
    logger.info("Customer records: %s", f"{len(customers):,}")
    logger.info(
        "Signup date range: %s to %s",
        customers["signup_date"].min(),
        customers["signup_date"].max(),
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