from __future__ import annotations

import logging

import pandas as pd

from customer_signup_util.customer_signup_validation import (
    validate_customer_references,
    validate_derived_signup_dates,
    validate_final_schema,
    validate_signup_date_coverage,
    validate_temporal_integrity,
    validate_unique_key,
)

logger = logging.getLogger(__name__)


def derive_signup_dates(orders: pd.DataFrame) -> pd.DataFrame:
    signup_dates = (
        orders.groupby("customer_id", as_index=False)[
            "order_purchase_timestamp"
        ]
        .min()
        .rename(columns={"order_purchase_timestamp": "signup_date"})
    )

    if signup_dates["signup_date"].isna().any():
        null_signup_dates = signup_dates["signup_date"].isna().sum()
        raise ValueError(
            f"{null_signup_dates:,} derived signup dates are NULL."
        )

    logger.info(
        "Signup dates derived for %s customers.",
        f"{len(signup_dates):,}",
    )

    return signup_dates


def enrich_customer_signup_dates(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
) -> pd.DataFrame:
    validate_unique_key(customers, "customer_id", "customers")

    if orders["order_id"].duplicated().any():
        duplicate_orders = orders["order_id"].duplicated().sum()
        raise ValueError(
            f"orders.order_id contains "
            f"{duplicate_orders:,} duplicate values."
        )

    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"],
        errors="coerce",
    )

    invalid_order_timestamps = (
        orders["order_purchase_timestamp"].isna().sum()
    )

    if invalid_order_timestamps > 0:
        raise ValueError(
            "Orders contain "
            f"{invalid_order_timestamps:,} invalid or NULL "
            "order_purchase_timestamp values."
        )

    logger.info("Order purchase timestamp parsing passed.")

    validate_customer_references(customers, orders)

    original_customer_count = len(customers)

    signup_dates = derive_signup_dates(orders)

    customers = customers.drop(columns=["signup_date"])

    enriched_customers = customers.merge(
        signup_dates,
        on="customer_id",
        how="left",
        validate="one_to_one",
    )

    if len(enriched_customers) != original_customer_count:
        raise ValueError(
            "Customer row count changed during signup date enrichment. "
            f"Expected {original_customer_count:,}, "
            f"got {len(enriched_customers):,}."
        )

    logger.info(
        "Customer row-count validation passed: %s records.",
        f"{len(enriched_customers):,}",
    )

    validate_signup_date_coverage(enriched_customers, signup_dates)
    validate_temporal_integrity(enriched_customers, orders)
    validate_derived_signup_dates(enriched_customers, orders)
    validate_unique_key(enriched_customers, "customer_id", "customers")
    validate_final_schema(enriched_customers)

    return enriched_customers