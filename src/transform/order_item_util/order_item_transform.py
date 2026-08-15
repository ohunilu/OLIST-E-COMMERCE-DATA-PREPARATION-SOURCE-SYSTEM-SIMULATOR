from __future__ import annotations

import pandas as pd

from order_item_util.order_item_temporal import (
    apply_temporal_shift,
    calculate_orders_offset,
)
from order_item_util.order_item_validation import (
    validate_numeric_values,
    validate_order_item_keys,
    validate_required_fields,
    validate_source_schema,
)

def transform_order_items(
    source_df: pd.DataFrame,
) -> pd.DataFrame:
    validate_source_schema(source_df)
    validate_order_item_keys(source_df)
    validate_required_fields(source_df)
    validate_numeric_values(source_df)

    offset = calculate_orders_offset()

    transformed = apply_temporal_shift(source_df, offset)

    return transformed