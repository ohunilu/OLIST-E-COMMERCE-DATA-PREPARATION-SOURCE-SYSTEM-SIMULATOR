from __future__ import annotations

import pandas as pd

from review_util.review_temporal import (
    apply_temporal_offset,
    calculate_simulation_offset,
    parse_timestamps,
    validate_timestamp_anchor,
)
from review_util.review_validation import (
    validate_order_reference,
    validate_output_key,
    validate_output_row_count,
    validate_required_fields,
    validate_review_chronology,
    validate_review_key,
    validate_review_scores,
    validate_source_schema,
    validate_orders_schema,
    validate_output_schema,
    validate_timestamp_null_preservation,
)

def transform_reviews(
    source_df: pd.DataFrame,
    orders_df: pd.DataFrame,
) -> pd.DataFrame:
    validate_source_schema(source_df)
    validate_orders_schema(orders_df)
    validate_review_key(source_df)
    validate_required_fields(source_df)

    source_df = parse_timestamps(source_df)

    validate_review_scores(source_df)
    validate_review_chronology(source_df)

    simulation_offset = calculate_simulation_offset(orders_df)

    transformed_df = apply_temporal_offset(
        source_df.copy(),
        simulation_offset,
    )

    validate_order_reference(
        transformed_df,
        orders_df,
    )

    validate_timestamp_anchor(
        transformed_df,
        simulation_offset,
    )

    validate_timestamp_null_preservation(
        source_df,
        transformed_df,
    )

    validate_output_row_count(
        source_df,
        transformed_df,
    )

    validate_output_key(
        transformed_df,
    )

    transformed_df = transformed_df[
        [
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ]
    ]

    validate_output_schema(transformed_df)

    return transformed_df