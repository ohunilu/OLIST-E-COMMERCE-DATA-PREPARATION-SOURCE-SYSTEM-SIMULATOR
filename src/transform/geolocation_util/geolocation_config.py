from pathlib import Path

SOURCE_FILE = Path("/app/source_data/olist_geolocation_dataset.csv")
OUTPUT_FILE = Path("/app/simulated_data/geolocation.csv")

EXPECTED_COLUMNS = [
    "geolocation_zip_code_prefix",
    "geolocation_lat",
    "geolocation_lng",
    "geolocation_city",
    "geolocation_state",
]

REQUIRED_COLUMNS = EXPECTED_COLUMNS

LATITUDE_MIN = -90.0
LATITUDE_MAX = 90.0

LONGITUDE_MIN = -180.0
LONGITUDE_MAX = 180.0