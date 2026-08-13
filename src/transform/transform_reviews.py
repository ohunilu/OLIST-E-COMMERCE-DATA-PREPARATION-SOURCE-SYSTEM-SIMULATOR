"""
Transform Olist order reviews dataset into simulated source-system data.

Source:
    /app/source_data/olist_order_reviews_dataset.csv

Reference:
    /app/simulated_data/orders.csv

Output:
    /app/simulated_data/reviews.csv

Purpose:
    - Preserve the Olist review dataset structure and business semantics.
    - Apply the same temporal simulation offset used by orders.csv.
    - Preserve duplicate review_id values because review_id alone is not unique
      in the source dataset.
    - Validate the composite review_id + order_id key.
    - Preserve NULL review title/message values.
    - Validate review scores and timestamps.
    - Validate that all referenced orders exist in the transformed orders dataset.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_FILE = Path(
    "/app/source_data/olist_order_reviews_dataset.csv"
)

ORDERS_REFERENCE_FILE = Path(
    "/app/simulated_data/orders.csv"
)

OUTPUT_FILE = Path(
    "/app/simulated_data/reviews.csv"
)

TIMESTAMP_COLUMNS = [
    "review_creation_date",
    "review_answer_timestamp",
]

EXPECTED_SOURCE_COLUMNS = [
    "review_id",
    "order_id",
    "review_score",
    "review_comment_title",
    "review_comment_message",
    "review_creation_date",
    "review_answer_timestamp",
]

EXPECTED_OUTPUT_COLUMNS = [
    "review_id",
    "order_id",
    "review_score",
    "review_comment_title",
    "review_comment_message",
    "review_creation_date",
    "review_answer_timestamp",
]

ORDERS_REQUIRED_COLUMNS = [
    "order_id",
    "order_purchase_timestamp",
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
# Utility functions
# ---------------------------------------------------------------------------

def validate_file_exists(path: Path, description: str) -> None:
    """Validate that an expected input file exists."""

    if not path.exists():
        raise FileNotFoundError(
            f"{description} not found: {path}"
        )


def validate_source_schema(df: pd.DataFrame) -> None:
    """Validate the source dataset schema."""

    actual_columns = list(df.columns)

    missing_columns = [
        column
        for column in EXPECTED_SOURCE_COLUMNS
        if column not in actual_columns
    ]

    unexpected_columns = [
        column
        for column in actual_columns
        if column not in EXPECTED_SOURCE_COLUMNS
    ]

    if missing_columns:
        raise ValueError(
            f"Source dataset is missing required columns: "
            f"{missing_columns}"
        )

    if unexpected_columns:
        logger.warning(
            "Source dataset contains unexpected columns: %s",
            unexpected_columns,
        )

    logger.info("Source schema validation passed.")


def validate_orders_schema(df: pd.DataFrame) -> None:
    """Validate the transformed orders reference schema."""

    missing_columns = [
        column
        for column in ORDERS_REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Orders reference is missing required columns: "
            f"{missing_columns}"
        )

    logger.info("Orders reference schema validation passed.")


def validate_review_key(df: pd.DataFrame) -> None:
    """
    Validate the review composite key.

    review_id is NOT unique in the Olist source dataset.
    The observed source grain is review_id + order_id.
    """

    duplicate_count = df.duplicated(
        subset=["review_id", "order_id"]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            "Duplicate review_id + order_id keys detected: "
            f"{duplicate_count}"
        )

    logger.info(
        "Composite review key validation passed."
    )


def validate_required_fields(df: pd.DataFrame) -> None:
    """Validate required non-null fields."""

    required_columns = [
        "review_id",
        "order_id",
        "review_score",
        "review_creation_date",
        "review_answer_timestamp",
    ]

    null_counts = df[required_columns].isna().sum()

    invalid = null_counts[null_counts > 0]

    if not invalid.empty:
        raise ValueError(
            "Required fields contain NULL values: "
            f"{invalid.to_dict()}"
        )

    logger.info(
        "Required field validation passed."
    )


def parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """Parse review timestamp columns into datetime values."""

    for column in TIMESTAMP_COLUMNS:
        df[column] = pd.to_datetime(
            df[column],
            errors="coerce",
        )

        invalid_count = df[column].isna().sum()

        if invalid_count > 0:
            raise ValueError(
                f"Invalid timestamps detected in {column}: "
                f"{invalid_count}"
            )

    logger.info(
        "Review timestamp parsing completed."
    )

    return df


def validate_review_scores(df: pd.DataFrame) -> None:
    """Validate review scores against the Olist 1–5 scale."""

    invalid_scores = ~df["review_score"].isin(
        [1, 2, 3, 4, 5]
    )

    invalid_count = invalid_scores.sum()

    if invalid_count > 0:
        raise ValueError(
            f"Invalid review scores detected: "
            f"{invalid_count}"
        )

    logger.info(
        "Review score validation passed."
    )


def validate_review_chronology(df: pd.DataFrame) -> None:
    """
    Validate chronology between review creation and answer timestamps.

    The expected relationship is:

        review_creation_date <= review_answer_timestamp
    """

    invalid = (
        df["review_creation_date"]
        > df["review_answer_timestamp"]
    )

    invalid_count = invalid.sum()

    if invalid_count > 0:
        logger.warning(
            "Source chronology anomaly: "
            "review_creation_date <= review_answer_timestamp | "
            "rows=%d",
            invalid_count,
        )

        # We deliberately preserve source anomalies rather than modifying
        # business data in the source-system simulator.
        logger.warning(
            "Review chronology anomalies preserved from source."
        )
    else:
        logger.info(
            "Review chronology check passed: "
            "creation <= answer"
        )


def calculate_simulation_offset(
    orders_df: pd.DataFrame,
) -> pd.Timedelta:
    """
    Calculate the temporal simulation offset from orders.csv.

    The transformed orders dataset establishes the authoritative
    simulation anchor used by all order-related datasets.
    """

    orders_purchase = pd.to_datetime(
        orders_df["order_purchase_timestamp"],
        errors="coerce",
    )

    if orders_purchase.isna().any():
        raise ValueError(
            "Orders reference contains invalid purchase timestamps."
        )

    source_orders = pd.read_csv(
        "/app/source_data/olist_orders_dataset.csv",
        usecols=["order_purchase_timestamp"],
    )

    source_orders["order_purchase_timestamp"] = pd.to_datetime(
        source_orders["order_purchase_timestamp"],
        errors="coerce",
    )

    if source_orders["order_purchase_timestamp"].isna().any():
        raise ValueError(
            "Source orders contain invalid purchase timestamps."
        )

    source_anchor = source_orders[
        "order_purchase_timestamp"
    ].max()

    simulation_anchor = orders_purchase.max()

    offset = simulation_anchor - source_anchor

    logger.info(
        "Source order purchase anchor: %s",
        source_anchor,
    )

    logger.info(
        "Simulation order purchase anchor: %s",
        simulation_anchor,
    )

    logger.info(
        "Using orders simulation offset: %s",
        offset,
    )

    logger.info(
        "Offset in days: %.6f",
        offset.total_seconds() / 86400,
    )

    return offset


def apply_temporal_offset(
    df: pd.DataFrame,
    offset: pd.Timedelta,
) -> pd.DataFrame:
    """Apply the orders simulation offset to review timestamps."""

    for column in TIMESTAMP_COLUMNS:
        df[column] = df[column] + offset

    logger.info(
        "Applied temporal offset to %d review timestamp columns.",
        len(TIMESTAMP_COLUMNS),
    )

    return df


def validate_order_reference(
    reviews_df: pd.DataFrame,
    orders_df: pd.DataFrame,
) -> None:
    """Validate that every review references an existing transformed order."""

    review_orders = set(
        reviews_df["order_id"].dropna().unique()
    )

    transformed_orders = set(
        orders_df["order_id"].dropna().unique()
    )

    missing_orders = review_orders - transformed_orders

    if missing_orders:
        logger.warning(
            "Reviews reference %d order IDs not present "
            "in transformed orders.",
            len(missing_orders),
        )

        logger.warning(
            "These source-system reference anomalies will be preserved."
        )
    else:
        logger.info(
            "Order reference validation passed."
        )


def validate_timestamp_anchor(
    transformed_df: pd.DataFrame,
    offset: pd.Timedelta,
) -> None:
    """
    Validate that timestamps were shifted exactly by the expected offset.

    This is performed by comparing against the original source data.
    """

    source_df = pd.read_csv(
        SOURCE_FILE,
        usecols=TIMESTAMP_COLUMNS,
    )

    for column in TIMESTAMP_COLUMNS:

        source_ts = pd.to_datetime(
            source_df[column],
            errors="coerce",
        )

        transformed_ts = transformed_df[column]

        expected_ts = source_ts + offset

        comparison = (
            expected_ts.reset_index(drop=True)
            == transformed_ts.reset_index(drop=True)
        )

        # NaT comparisons evaluate to False, so explicitly preserve
        # NULL equality where applicable.
        both_null = (
            source_ts.isna()
            & transformed_ts.isna()
        )

        valid = comparison | both_null

        if not valid.all():
            invalid_count = (~valid).sum()

            raise ValueError(
                f"Temporal offset validation failed for "
                f"{column}: {invalid_count} rows."
            )

    logger.info(
        "Temporal offset validation passed."
    )


def validate_timestamp_null_preservation(
    source_df: pd.DataFrame,
    transformed_df: pd.DataFrame,
) -> None:
    """Ensure NULL timestamp patterns are preserved."""

    for column in TIMESTAMP_COLUMNS:

        source_nulls = source_df[column].isna().sum()
        transformed_nulls = transformed_df[column].isna().sum()

        if source_nulls != transformed_nulls:
            raise ValueError(
                f"Timestamp NULL preservation failed for {column}: "
                f"source={source_nulls}, "
                f"output={transformed_nulls}"
            )

    logger.info(
        "Timestamp NULL preservation validation passed."
    )


def validate_output_schema(df: pd.DataFrame) -> None:
    """Validate final output schema and column ordering."""

    actual_columns = list(df.columns)

    if actual_columns != EXPECTED_OUTPUT_COLUMNS:
        raise ValueError(
            "Output schema mismatch.\n"
            f"Expected: {EXPECTED_OUTPUT_COLUMNS}\n"
            f"Actual:   {actual_columns}"
        )

    logger.info(
        "Output schema validation passed."
    )


def validate_output_row_count(
    source_df: pd.DataFrame,
    transformed_df: pd.DataFrame,
) -> None:
    """Ensure no records were added or removed."""

    if len(source_df) != len(transformed_df):
        raise ValueError(
            "Output row count does not match source.\n"
            f"Source: {len(source_df)}\n"
            f"Output: {len(transformed_df)}"
        )

    logger.info(
        "Output row-count validation passed: %d records.",
        len(transformed_df),
    )


def validate_output_key(df: pd.DataFrame) -> None:
    """Validate the output composite key."""

    duplicate_count = df.duplicated(
        subset=["review_id", "order_id"]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            "Output contains duplicate review_id + order_id keys: "
            f"{duplicate_count}"
        )

    logger.info(
        "Output review key validation passed."
    )


# ---------------------------------------------------------------------------
# Main transformation
# ---------------------------------------------------------------------------

def main() -> None:
    """Execute the complete review transformation pipeline."""

    logger.info(
        "Starting Olist order reviews dataset transformation."
    )

    # -----------------------------------------------------------------------
    # Validate input files
    # -----------------------------------------------------------------------

    validate_file_exists(
        SOURCE_FILE,
        "Review source file",
    )

    validate_file_exists(
        ORDERS_REFERENCE_FILE,
        "Transformed orders reference",
    )

    # -----------------------------------------------------------------------
    # Read source data
    # -----------------------------------------------------------------------

    logger.info(
        "Reading source file: %s",
        SOURCE_FILE,
    )

    source_df = pd.read_csv(
        SOURCE_FILE,
        keep_default_na=True,
    )

    logger.info(
        "Source records loaded: %s",
        f"{len(source_df):,}",
    )

    # -----------------------------------------------------------------------
    # Read transformed orders reference
    # -----------------------------------------------------------------------

    logger.info(
        "Reading transformed orders reference: %s",
        ORDERS_REFERENCE_FILE,
    )

    orders_df = pd.read_csv(
        ORDERS_REFERENCE_FILE,
        usecols=ORDERS_REQUIRED_COLUMNS,
    )

    logger.info(
        "Orders reference records loaded: %s",
        f"{len(orders_df):,}",
    )

    # -----------------------------------------------------------------------
    # Schema validation
    # -----------------------------------------------------------------------

    validate_source_schema(source_df)
    validate_orders_schema(orders_df)

    # -----------------------------------------------------------------------
    # Key validation
    # -----------------------------------------------------------------------

    validate_review_key(source_df)

    # -----------------------------------------------------------------------
    # Required field validation
    # -----------------------------------------------------------------------

    validate_required_fields(source_df)

    # -----------------------------------------------------------------------
    # Timestamp parsing
    # -----------------------------------------------------------------------

    source_df = parse_timestamps(source_df)

    # -----------------------------------------------------------------------
    # Review score validation
    # -----------------------------------------------------------------------

    validate_review_scores(source_df)

    logger.info(
        "Review score distribution: %s",
        source_df["review_score"]
        .value_counts()
        .sort_index()
        .to_dict(),
    )

    # -----------------------------------------------------------------------
    # Source chronology validation
    # -----------------------------------------------------------------------

    validate_review_chronology(source_df)

    # -----------------------------------------------------------------------
    # Calculate authoritative simulation offset
    # -----------------------------------------------------------------------

    simulation_offset = calculate_simulation_offset(
        orders_df
    )

    # -----------------------------------------------------------------------
    # Apply simulation offset
    # -----------------------------------------------------------------------

    transformed_df = source_df.copy()

    transformed_df = apply_temporal_offset(
        transformed_df,
        simulation_offset,
    )

    # -----------------------------------------------------------------------
    # Validate order references
    # -----------------------------------------------------------------------

    validate_order_reference(
        transformed_df,
        orders_df,
    )

    # -----------------------------------------------------------------------
    # Validate temporal transformation
    # -----------------------------------------------------------------------

    validate_timestamp_anchor(
        transformed_df,
        simulation_offset,
    )

    validate_timestamp_null_preservation(
        source_df,
        transformed_df,
    )

    # -----------------------------------------------------------------------
    # Output schema and integrity validation
    # -----------------------------------------------------------------------

    validate_output_row_count(
        source_df,
        transformed_df,
    )

    validate_output_key(
        transformed_df,
    )

    # -----------------------------------------------------------------------
    # Reorder columns
    # -----------------------------------------------------------------------

    transformed_df = transformed_df[
        EXPECTED_OUTPUT_COLUMNS
    ]

    validate_output_schema(
        transformed_df,
    )

    # -----------------------------------------------------------------------
    # Write output
    # -----------------------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    transformed_df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    logger.info(
        "Output file written: %s",
        OUTPUT_FILE,
    )

    # -----------------------------------------------------------------------
    # Final summary
    # -----------------------------------------------------------------------

    logger.info(
        "Review transformation completed successfully."
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
        "Source review creation range: %s to %s",
        source_df["review_creation_date"].min(),
        source_df["review_creation_date"].max(),
    )

    logger.info(
        "Simulation review creation range: %s to %s",
        transformed_df["review_creation_date"].min(),
        transformed_df["review_creation_date"].max(),
    )

    logger.info(
        "Simulation offset: %s",
        simulation_offset,
    )

    logger.info(
        "Output file: %s",
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    main()