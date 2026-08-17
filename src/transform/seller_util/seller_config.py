from pathlib import Path

SOURCE_FILE = Path("/app/source_data/olist_sellers_dataset.csv")
OUTPUT_FILE = Path("/app/simulated_data/sellers.csv")

EXPECTED_COLUMNS = [
    "seller_id",
    "seller_zip_code_prefix",
    "seller_city",
    "seller_state",
]

VALID_STATE_LENGTH = 2