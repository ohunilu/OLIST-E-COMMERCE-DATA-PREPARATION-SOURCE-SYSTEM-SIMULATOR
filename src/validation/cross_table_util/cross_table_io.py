from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from cross_table_util.cross_table_config import (
    CUSTOMERS_FILE,
    GEOLOCATION_FILE,
    ORDER_ITEMS_FILE,
    ORDERS_FILE,
    PAYMENTS_FILE,
    PRODUCTS_FILE,
    REVIEWS_FILE,
    SELLERS_FILE,
)

logger = logging.getLogger(__name__)


def load_table(path: Path, table_name: str) -> pd.DataFrame:
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


def load_all_tables() -> dict[str, pd.DataFrame]:
    return {
        "customers": load_table(CUSTOMERS_FILE, "customers"),
        "orders": load_table(ORDERS_FILE, "orders"),
        "order_items": load_table(ORDER_ITEMS_FILE, "order_items"),
        "products": load_table(PRODUCTS_FILE, "products"),
        "payments": load_table(PAYMENTS_FILE, "payments"),
        "sellers": load_table(SELLERS_FILE, "sellers"),
        "reviews": load_table(REVIEWS_FILE, "reviews"),
        "geolocation": load_table(GEOLOCATION_FILE, "geolocation"),
    }