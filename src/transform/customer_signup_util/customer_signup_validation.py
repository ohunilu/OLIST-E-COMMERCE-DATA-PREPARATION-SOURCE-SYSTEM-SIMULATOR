from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def validate_required_columns(
    dataframe: pd.DataFrame,
    required_columns: list[str],
    table_name: str,
) -> None:
    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"{table_name} is missing required columns: {missing_columns}"
        )

    logger.info("%s schema validation passed.", table_name)


def validate_unique_key(
    dataframe: pd.DataFrame,
    column: str,
    table_name: str,
) -> None:
    duplicate_count = dataframe[column].duplicated().sum()

    if duplicate_count > 0:
        raise ValueError(
            f"{table_name}.{column} contains "
            f"{duplicate_count:,} duplicate values."
        )

    logger.info("%s key validation passed.", table_name)


def validate_customer_references(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
) -> None:
    customer_ids = set(customers["customer_id"])
    order_customer_ids = set(orders["customer_id"].dropna())

    unknown_customer_ids = order_customer_ids - customer_ids

    if unknown_customer_ids:
        logger.error(
            "Orders contain %s customer_id values that do not exist "
            "in customers.",
            f"{len(unknown_customer_ids):,}",
        )

        sample = list(unknown_customer_ids)[:10]

        raise ValueError(
            "Order-to-customer referential integrity validation failed. "
            f"Sample unknown customer IDs: {sample}"
        )

    logger.info("Order-to-customer reference validation passed.")


def validate_temporal_integrity(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
) -> None:
    validation_frame = orders[
        ["customer_id", "order_purchase_timestamp"]
    ].merge(
        customers[["customer_id", "signup_date"]],
        on="customer_id",
        how="left",
        validate="many_to_one",
    )

    invalid_count = (
        validation_frame["signup_date"]
        > validation_frame["order_purchase_timestamp"]
    ).sum()

    if invalid_count > 0:
        raise ValueError(
            "Temporal integrity validation failed: "
            f"{invalid_count:,} orders have a purchase timestamp "
            "earlier than customer signup_date."
        )

    logger.info(
        "Temporal integrity validation passed: signup_date <= order_purchase_timestamp."
    )


def validate_signup_date_coverage(
    customers: pd.DataFrame,
    signup_dates: pd.DataFrame,
) -> None:
    customers_with_orders = customers["customer_id"].isin(
        signup_dates["customer_id"]
    )

    missing_signup_dates = (
        customers.loc[
            customers_with_orders,
            "signup_date",
        ].isna().sum()
    )

    if missing_signup_dates > 0:
        raise ValueError(
            f"{missing_signup_dates:,} customers with orders "
            "have NULL signup_date values."
        )

    logger.info(
        "Customers with orders: %s",
        f"{customers_with_orders.sum():,}",
    )

    logger.info(
        "Customers without orders: %s",
        f"{(~customers_with_orders).sum():,}",
    )


def validate_derived_signup_dates(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
) -> None:
    expected_signup_dates = (
        orders.groupby("customer_id")["order_purchase_timestamp"]
        .min()
        .rename("expected_signup_date")
    )

    comparison = customers[
        ["customer_id", "signup_date"]
    ].merge(
        expected_signup_dates,
        left_on="customer_id",
        right_index=True,
        how="inner",
        validate="one_to_one",
    )

    mismatched_signup_dates = (
        comparison["signup_date"]
        != comparison["expected_signup_date"]
    ).sum()

    if mismatched_signup_dates > 0:
        raise ValueError(
            "Signup date derivation validation failed: "
            f"{mismatched_signup_dates:,} customers have a signup_date "
            "different from their earliest purchase timestamp."
        )

    logger.info(
        "Signup date derivation validation passed: signup_date equals earliest purchase timestamp."
    )


def validate_final_schema(customers: pd.DataFrame) -> None:
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
        "zip_code_prefix",
        "country",
        "signup_date",
    ]

    if list(customers.columns) != expected_columns:
        raise ValueError(
            "Output customer schema validation failed.\n"
            f"Expected: {expected_columns}\n"
            f"Actual:   {customers.columns.tolist()}"
        )

    logger.info("Output customer schema validation passed.")