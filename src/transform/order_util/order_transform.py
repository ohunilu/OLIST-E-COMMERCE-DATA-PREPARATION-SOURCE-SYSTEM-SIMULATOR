from __future__ import annotations

import pandas as pd

from order_util.order_timestamps import (
    calculate_simulation_offset,
    parse_timestamps,
    shift_timestamps,
    standardize_order_status,
)
from order_util.order_validation import (
    validate_purchase_timestamps,
)

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

    df = parse_timestamps(df)

    validate_purchase_timestamps(df)

    offset, source_anchor = calculate_simulation_offset(df)

    df = shift_timestamps(df, offset)

    df = standardize_order_status(df)

    return df, offset, source_anchor