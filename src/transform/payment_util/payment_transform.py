from __future__ import annotations

import pandas as pd

from payment_util.payment_validation import (
    log_payment_statistics,
    standardize_payment_type,
    validate_numeric_values,
    validate_order_references,
    validate_output,
    validate_payment_keys,
    validate_required_fields,
    validate_source_schema,
)

def transform_payments(
    payments_df: pd.DataFrame,
    orders_df: pd.DataFrame,
) -> pd.DataFrame:
    validate_source_schema(payments_df)
    validate_payment_keys(payments_df)
    validate_required_fields(payments_df)

    payments_df = standardize_payment_type(payments_df)

    validate_numeric_values(payments_df)
    validate_order_references(payments_df, orders_df)
    log_payment_statistics(payments_df)
    validate_output(payments_df)

    return payments_df