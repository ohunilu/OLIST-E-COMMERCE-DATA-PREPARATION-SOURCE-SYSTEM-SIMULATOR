from pathlib import Path

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