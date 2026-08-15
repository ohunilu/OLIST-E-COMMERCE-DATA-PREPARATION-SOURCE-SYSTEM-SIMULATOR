from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from customer_util.customer_transform import (
    transform_customers as _transform_customers,
)
from customer_util.customer_synthetic import (
    deterministic_seed as _deterministic_seed,
    generate_synthetic_pii as _generate_synthetic_pii,
)
from customer_util.customer_validation import (
    validate_customer_keys as _validate_customer_keys,
    validate_output as _validate_output,
    validate_source_schema as _validate_source_schema,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_FILE = Path("/app/source_data/olist_customers_dataset.csv")
OUTPUT_FILE = Path("/app/simulated_data/customers.csv")

REQUIRED_COLUMNS = {
    "customer_id",
    "customer_unique_id",
    "customer_zip_code_prefix",
    "customer_city",
    "customer_state",
}

COUNTRY = "Brazil"

EXPECTED_OUTPUT_COLUMNS = [
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

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

def deterministic_seed(value: str) -> int:
    return _deterministic_seed(value)


def generate_synthetic_pii(customer_unique_id: str) -> dict[str, str]:
    logger.info("Generating deterministic synthetic customer PII...")
    return _generate_synthetic_pii(customer_unique_id)


def validate_source_schema(df: pd.DataFrame) -> None:
    _validate_source_schema(df, REQUIRED_COLUMNS)


def validate_customer_keys(df: pd.DataFrame) -> None:
    _validate_customer_keys(df)


def transform_customers(df: pd.DataFrame) -> pd.DataFrame:
    return _transform_customers(df, country=COUNTRY)


def validate_output(df: pd.DataFrame) -> None:
    _validate_output(df, EXPECTED_OUTPUT_COLUMNS)


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("Starting customer dataset transformation.")

    if not SOURCE_FILE.exists():
        raise FileNotFoundError(
            f"Source file not found: {SOURCE_FILE}"
        )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger.info("Reading source file: %s", SOURCE_FILE)

    source_df = pd.read_csv(SOURCE_FILE)

    logger.info(
        "Source records loaded: %s",
        f"{len(source_df):,}",
    )

    validate_source_schema(source_df)
    validate_customer_keys(source_df)

    transformed_df = transform_customers(source_df)

    validate_output(transformed_df)

    transformed_df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    logger.info(
        "Customer transformation completed successfully."
    )

    logger.info(
        "Output records: %s",
        f"{len(transformed_df):,}",
    )

    logger.info(
        "Output file: %s",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()