from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_FILE = Path("/app/source_data/olist_orders_dataset.csv")
OUTPUT_FILE = Path("/app/simulated_data/orders.csv")

# Fixed simulation clock.
# Keeping this deterministic ensures that repeated executions produce
# the same simulated timestamps.
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


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source Validation
# ---------------------------------------------------------------------------

def validate_source_schema(df: pd.DataFrame) -> None:
    """Validate that the source contains the expected columns."""

    actual_columns = set(df.columns)

    missing_columns = REQUIRED_COLUMNS - actual_columns

    if missing_columns:
        raise ValueError(
            "Source file is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    logger.info("Source schema validation passed.")


def validate_source_keys(df: pd.DataFrame) -> None:
    """Validate order and customer identifiers."""

    if df["order_id"].isna().any():
        raise ValueError("order_id contains NULL values.")

    if df["customer_id"].isna().any():
        raise ValueError("customer_id contains NULL values.")

    duplicate_order_ids = df["order_id"].duplicated().sum()

    if duplicate_order_ids > 0:
        raise ValueError(
            f"Found {duplicate_order_ids} duplicate order_id values."
        )

    logger.info("Order key validation passed.")


# ---------------------------------------------------------------------------
# Timestamp Parsing
# ---------------------------------------------------------------------------

def parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert all order lifecycle timestamp columns to pandas datetime.

    Invalid timestamps are converted to NaT. We subsequently validate
    the purchase timestamp because it is required for every order.
    """

    result = df.copy()

    for column in TIMESTAMP_COLUMNS:
        result[column] = pd.to_datetime(
            result[column],
            errors="coerce",
        )

    logger.info("Timestamp parsing completed.")

    return result


def validate_purchase_timestamps(df: pd.DataFrame) -> None:
    """Ensure every order has a valid purchase timestamp."""

    missing_purchase_dates = df["order_purchase_timestamp"].isna().sum()

    if missing_purchase_dates > 0:
        raise ValueError(
            "Found "
            f"{missing_purchase_dates:,} orders with invalid or missing "
            "order_purchase_timestamp."
        )

    logger.info("Purchase timestamp validation passed.")


# ---------------------------------------------------------------------------
# Temporal Simulation
# ---------------------------------------------------------------------------

def calculate_simulation_offset(
    df: pd.DataFrame,
) -> tuple[pd.Timedelta, pd.Timestamp]:
    """
    Calculate the deterministic temporal offset.

    The latest source purchase timestamp becomes SIMULATION_AS_OF.
    """

    source_anchor = df["order_purchase_timestamp"].max()

    if pd.isna(source_anchor):
        raise ValueError(
            "Unable to calculate simulation anchor. "
            "No valid purchase timestamps were found."
        )

    offset = SIMULATION_AS_OF - source_anchor

    logger.info(
        "Source purchase anchor: %s",
        source_anchor,
    )

    logger.info(
        "Simulation as-of: %s",
        SIMULATION_AS_OF,
    )

    logger.info(
        "Calculated simulation offset: %s",
        offset,
    )

    logger.info(
        "Offset in days: %.6f",
        offset.total_seconds() / 86400,
    )

    return offset, source_anchor


def shift_timestamps(
    df: pd.DataFrame,
    offset: pd.Timedelta,
) -> pd.DataFrame:
    """
    Apply the same temporal offset to every non-null lifecycle timestamp.

    NULL timestamps remain NULL.
    """

    result = df.copy()

    for column in TIMESTAMP_COLUMNS:
        result[column] = result[column] + offset

    logger.info(
        "Applied identical temporal offset to %d timestamp columns.",
        len(TIMESTAMP_COLUMNS),
    )

    return result


# ---------------------------------------------------------------------------
# Status Standardization
# ---------------------------------------------------------------------------

def standardize_order_status(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize order status values."""

    result = df.copy()

    result["order_status"] = (
        result["order_status"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    logger.info(
        "Order status standardization completed."
    )

    logger.info(
        "Order statuses found: %s",
        sorted(result["order_status"].dropna().unique().tolist()),
    )

    return result


# ---------------------------------------------------------------------------
# Chronological Validation
# ---------------------------------------------------------------------------

def validate_event_chronology(df: pd.DataFrame) -> dict[str, int]:
    """
    Profile order lifecycle chronology.

    Chronology violations that already exist in the source are treated
    as source data-quality anomalies rather than transformation failures.

    The transformation preserves these anomalies intentionally so that
    the simulated source retains realistic operational data quality.
    """

    chronology_rules = [
        (
            "order_purchase_timestamp",
            "order_approved_at",
            "purchase <= approved",
        ),
        (
            "order_approved_at",
            "order_delivered_carrier_date",
            "approved <= carrier",
        ),
        (
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "carrier <= delivered",
        ),
        (
            "order_purchase_timestamp",
            "order_estimated_delivery_date",
            "purchase <= estimated_delivery",
        ),
    ]

    anomaly_counts = {}

    for earlier_column, later_column, description in chronology_rules:

        mask = (
            df[earlier_column].notna()
            & df[later_column].notna()
            & (df[earlier_column] > df[later_column])
        )

        violations = int(mask.sum())

        anomaly_counts[description] = violations

        if violations > 0:
            logger.warning(
                "Source chronology anomaly: %s | rows=%s",
                description,
                f"{violations:,}",
            )
        else:
            logger.info(
                "Chronology check passed: %s",
                description,
            )

    total_anomalies = sum(anomaly_counts.values())

    if total_anomalies > 0:
        logger.warning(
            "Total source chronology anomalies preserved: %s",
            f"{total_anomalies:,}",
        )
    else:
        logger.info(
            "No source chronology anomalies detected."
        )

    return anomaly_counts


# ---------------------------------------------------------------------------
# Temporal Integrity Validation
# ---------------------------------------------------------------------------

def validate_temporal_anchor(
    df: pd.DataFrame,
    expected_anchor: pd.Timestamp,
) -> None:
    """
    Confirm that the latest simulated purchase timestamp equals
    the configured simulation reference timestamp.
    """

    actual_anchor = df["order_purchase_timestamp"].max()

    if actual_anchor != expected_anchor:
        raise ValueError(
            "Simulation anchor validation failed. "
            f"Expected {expected_anchor}, got {actual_anchor}."
        )

    logger.info(
        "Simulation anchor validation passed: %s",
        actual_anchor,
    )


def validate_null_preservation(
    source_df: pd.DataFrame,
    transformed_df: pd.DataFrame,
) -> None:
    """
    Ensure that timestamp NULLs were not converted into artificial dates.
    """

    for column in TIMESTAMP_COLUMNS:

        source_nulls = int(source_df[column].isna().sum())
        transformed_nulls = int(transformed_df[column].isna().sum())

        if source_nulls != transformed_nulls:
            raise ValueError(
                f"NULL preservation failed for {column}. "
                f"Source NULLs={source_nulls}, "
                f"Transformed NULLs={transformed_nulls}."
            )

    logger.info(
        "Timestamp NULL preservation validation passed."
    )


# ---------------------------------------------------------------------------
# Output Validation
# ---------------------------------------------------------------------------

def validate_output(df: pd.DataFrame) -> None:
    """Validate the final transformed orders dataset."""

    expected_columns = [
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]

    if list(df.columns) != expected_columns:
        raise ValueError(
            "Output schema does not match expected schema.\n"
            f"Expected: {expected_columns}\n"
            f"Actual:   {list(df.columns)}"
        )

    if df["order_id"].isna().any():
        raise ValueError(
            "Transformed order_id contains NULL values."
        )

    if df["customer_id"].isna().any():
        raise ValueError(
            "Transformed customer_id contains NULL values."
        )

    if df["order_id"].duplicated().any():
        raise ValueError(
            "Transformed order_id contains duplicate values."
        )

    if df["order_purchase_timestamp"].isna().any():
        raise ValueError(
            "Transformed order_purchase_timestamp contains NULL values."
        )

    logger.info("Output schema validation passed.")


# ---------------------------------------------------------------------------
# Transformation
# ---------------------------------------------------------------------------

def transform_orders(
    source_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Timedelta, pd.Timestamp]:
    """
    Execute the complete orders transformation.

    Returns:
        transformed dataframe
        simulation offset
        source purchase anchor
    """

    df = source_df.copy()

    # Parse timestamps before calculating the source anchor.
    df = parse_timestamps(df)

    validate_purchase_timestamps(df)

    # Determine the temporal translation from the source data itself.
    offset, source_anchor = calculate_simulation_offset(df)

    # Apply identical offset to every timestamp.
    df = shift_timestamps(df, offset)

    # Standardize categorical status.
    df = standardize_order_status(df)

    return df, offset, source_anchor


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info(
        "Starting Olist orders dataset transformation."
    )

    # -----------------------------------------------------------------------
    # Check source
    # -----------------------------------------------------------------------

    if not SOURCE_FILE.exists():
        raise FileNotFoundError(
            f"Source file not found: {SOURCE_FILE}"
        )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -----------------------------------------------------------------------
    # Read source
    # -----------------------------------------------------------------------

    logger.info(
        "Reading source file: %s",
        SOURCE_FILE,
    )

    source_df = pd.read_csv(SOURCE_FILE)

    logger.info(
        "Source records loaded: %s",
        f"{len(source_df):,}",
    )

    # -----------------------------------------------------------------------
    # Source validation
    # -----------------------------------------------------------------------

    validate_source_schema(source_df)
    validate_source_keys(source_df)

    # -----------------------------------------------------------------------
    # Transformation
    # -----------------------------------------------------------------------

    transformed_df, offset, source_anchor = transform_orders(
        source_df
    )

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    validate_event_chronology(transformed_df)

    validate_temporal_anchor(
        transformed_df,
        SIMULATION_AS_OF,
    )

    validate_null_preservation(
        source_df.assign(
            **{
                column: pd.to_datetime(
                    source_df[column],
                    errors="coerce",
                )
                for column in TIMESTAMP_COLUMNS
            }
        ),
        transformed_df,
    )

    validate_output(transformed_df)

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------

    transformed_df.to_csv(
        OUTPUT_FILE,
        index=False,
        date_format="%Y-%m-%d %H:%M:%S",
    )

    logger.info(
        "Orders transformation completed successfully."
    )

    logger.info(
        "Source records: %s",
        f"{len(source_df):,}",
    )

    logger.info(
        "Output records: %s",
        f"{len(transformed_df):,}",
    )

    logger.info(
        "Source purchase anchor: %s",
        source_anchor,
    )

    logger.info(
        "Simulation anchor: %s",
        SIMULATION_AS_OF,
    )

    logger.info(
        "Simulation offset: %s",
        offset,
    )

    logger.info(
        "Output file: %s",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()