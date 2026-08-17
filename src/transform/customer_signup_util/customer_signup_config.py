from pathlib import Path

BASE_DIR = Path("/app")

CUSTOMERS_FILE = BASE_DIR / "simulated_data" / "customers.csv"
ORDERS_FILE = BASE_DIR / "simulated_data" / "orders.csv"

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"

EXPECTED_CUSTOMER_COLUMNS = [
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

EXPECTED_ORDER_COLUMNS = [
    "order_id",
    "customer_id",
    "order_purchase_timestamp",
]