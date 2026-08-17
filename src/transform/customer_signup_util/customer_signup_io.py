from __future__ import annotations

import logging

import pandas as pd

from customer_signup_util.customer_signup_config import (
    CUSTOMERS_FILE,
    ORDERS_FILE,
)

logger = logging.getLogger(__name__)


def read_customers() -> pd.DataFrame:
    logger.info("Reading customers: %s", CUSTOMERS_FILE)

    customers = pd.read_csv(CUSTOMERS_FILE)

    logger.info(
        "Customer records loaded: %s",
        f"{len(customers):,}",
    )

    return customers


def read_orders() -> pd.DataFrame:
    logger.info("Reading transformed orders reference: %s", ORDERS_FILE)

    orders = pd.read_csv(ORDERS_FILE)

    logger.info(
        "Order records loaded: %s",
        f"{len(orders):,}",
    )

    return orders


def write_customers(customers: pd.DataFrame) -> None:
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