from pathlib import Path

import pandas as pd

SOURCE_FILE = Path("/app/source_data/olist_orders_dataset.csv")
OUTPUT_FILE = Path("/app/simulated_data/orders.csv")

SIMULATION_AS_OF = pd.Timestamp("2026-08-12 23:59:59")

REQUIRED_COLUMNS = {
    "order_id",
    "customer_id",
    "order_status",
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
}

TIMESTAMP_COLUMNS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]

EXPECTED_OUTPUT_COLUMNS = [
    "order_id",
    "customer_id",
    "order_status",
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]