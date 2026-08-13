from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pandas as pd
from faker import Faker


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


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Deterministic Faker
# ---------------------------------------------------------------------------

def deterministic_seed(value: str) -> int:
    """
    Generate a stable integer seed from a customer identifier.

    The same customer identifier will always produce the same seed,
    ensuring deterministic synthetic PII across pipeline executions.
    """
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()

    # Use the first 16 hexadecimal characters to create a stable integer.
    return int(digest[:16], 16)


def generate_synthetic_pii(customer_unique_id: str) -> dict[str, str]:
    """
    Generate deterministic synthetic customer PII.

    The generated email uses the reserved .test domain so that it cannot
    accidentally represent a real production email address.
    """

    fake = Faker("pt_BR")
    fake.seed_instance(deterministic_seed(customer_unique_id))

    first_name = fake.first_name()
    last_name = fake.last_name()

    # Normalize names for use in the synthetic email address.
    first_normalized = (
        first_name.lower()
        .replace(" ", ".")
    )

    last_normalized = (
        last_name.lower()
        .replace(" ", ".")
    )

    email = (
        f"{first_normalized}.{last_normalized}."
        f"{customer_unique_id[:8]}@example.test"
    )

    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": fake.phone_number(),
        "address_line_1": fake.street_address(),
    }


# ---------------------------------------------------------------------------
# Source Validation
# ---------------------------------------------------------------------------

def validate_source_schema(df: pd.DataFrame) -> None:
    """Validate that the source contains the expected columns."""

    actual_columns = set(df.columns)

    missing_columns = REQUIRED_COLUMNS - actual_columns

    if missing_columns:
        raise ValueError(
            f"Source file is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    logger.info("Source schema validation passed.")


def validate_customer_keys(df: pd.DataFrame) -> None:
    """Validate customer identifiers."""

    if df["customer_id"].isna().any():
        raise ValueError("customer_id contains NULL values.")

    if df["customer_unique_id"].isna().any():
        raise ValueError("customer_unique_id contains NULL values.")

    duplicate_customer_ids = df["customer_id"].duplicated().sum()

    if duplicate_customer_ids > 0:
        raise ValueError(
            f"Found {duplicate_customer_ids} duplicate customer_id values."
        )

    logger.info("Customer key validation passed.")


# ---------------------------------------------------------------------------
# Transformation
# ---------------------------------------------------------------------------

def transform_customers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform the raw Olist customer dataset into the simulated
    operational customer model.
    """

    output = pd.DataFrame()

    # -----------------------------------------------------------------------
    # Preserve source identifiers
    # -----------------------------------------------------------------------

    output["customer_id"] = (
        df["customer_id"]
        .astype("string")
        .str.strip()
    )

    output["customer_unique_id"] = (
        df["customer_unique_id"]
        .astype("string")
        .str.strip()
    )

    # -----------------------------------------------------------------------
    # Generate deterministic synthetic PII
    # -----------------------------------------------------------------------

    logger.info("Generating deterministic synthetic customer PII...")

    pii_records = [
        generate_synthetic_pii(customer_unique_id)
        for customer_unique_id in output["customer_unique_id"]
    ]

    pii_df = pd.DataFrame(pii_records)

    output = pd.concat(
        [output.reset_index(drop=True), pii_df],
        axis=1,
    )

    # -----------------------------------------------------------------------
    # Geography
    # -----------------------------------------------------------------------

    output["city"] = (
        df["customer_city"]
        .astype("string")
        .str.strip()
        .str.title()
    )

    output["state"] = (
        df["customer_state"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    output["postal_code"] = (
        df["customer_zip_code_prefix"]
        .astype("string")
        .str.zfill(5)
    )

    output["country"] = COUNTRY

    # -----------------------------------------------------------------------
    # Customer lifecycle timestamps
    # -----------------------------------------------------------------------

    # Olist does not contain a customer signup timestamp.
    # This will be populated later using the customer's earliest order.
    output["signup_date"] = pd.NaT

    # These are operational metadata fields. We will establish the actual
    # simulation clock when the full source-system preparation pipeline
    # is implemented.
    output["created_at"] = pd.NaT
    output["updated_at"] = pd.NaT

    return output


# ---------------------------------------------------------------------------
# Output Validation
# ---------------------------------------------------------------------------

def validate_output(df: pd.DataFrame) -> None:
    """Validate the transformed customer dataset."""

    expected_columns = [
        "customer_id",
        "customer_unique_id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "address_line_1",
        "city",
        "state",
        "postal_code",
        "country",
        "signup_date",
        "created_at",
        "updated_at",
    ]

    if list(df.columns) != expected_columns:
        raise ValueError(
            "Output schema does not match expected schema.\n"
            f"Expected: {expected_columns}\n"
            f"Actual:   {list(df.columns)}"
        )

    if df["customer_id"].isna().any():
        raise ValueError("Transformed customer_id contains NULL values.")

    if df["customer_unique_id"].isna().any():
        raise ValueError(
            "Transformed customer_unique_id contains NULL values."
        )

    if df["customer_id"].duplicated().any():
        raise ValueError(
            "Transformed customer_id contains duplicate values."
        )

    if not df["email"].str.endswith("@example.test").all():
        raise ValueError(
            "Synthetic email validation failed. "
            "All generated emails must use @example.test."
        )

    if not (df["state"].str.len() == 2).all():
        raise ValueError(
            "Customer state validation failed. "
            "Expected two-character Brazilian state codes."
        )

    if not (df["postal_code"].str.len() == 5).all():
        raise ValueError(
            "Postal code validation failed. "
            "Expected five-character postal codes."
        )

    customer_mapping = (
        df.groupby("customer_unique_id")["customer_id"]
        .nunique()
    )

    if customer_mapping.empty:
        raise ValueError(
            "No customer identity mappings were found."
        )

    logger.info(
        "Persistent customer identities: %s",
        f"{customer_mapping.shape[0]:,}",
    )

    logger.info(
        "Customer records mapped to multiple customer_id values: %s",
        f"{(customer_mapping > 1).sum():,}",
    )

    logger.info("Output validation passed.")


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