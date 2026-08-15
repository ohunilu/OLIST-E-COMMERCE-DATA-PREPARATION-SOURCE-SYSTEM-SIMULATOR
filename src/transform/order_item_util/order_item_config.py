from pathlib import Path

import pandas as pd

SOURCE_FILE = Path("/app/source_data/olist_order_items_dataset.csv")
ORDERS_SOURCE_FILE = Path("/app/source_data/olist_orders_dataset.csv")
OUTPUT_FILE = Path("/app/simulated_data/order_items.csv")

SIMULATION_AS_OF = pd.Timestamp("2026-08-12 23:59:59")

REQUIRED_COLUMNS = {
    "order_id",
    "order_item_id",
    "product_id",
    "seller_id",
    "shipping_limit_date",
    "price",
    "freight_value",
}