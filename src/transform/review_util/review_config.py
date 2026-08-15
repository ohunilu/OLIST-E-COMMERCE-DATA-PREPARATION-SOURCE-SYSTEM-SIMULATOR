from pathlib import Path

SOURCE_FILE = Path("/app/source_data/olist_order_reviews_dataset.csv")
ORDERS_REFERENCE_FILE = Path("/app/simulated_data/orders.csv")
OUTPUT_FILE = Path("/app/simulated_data/reviews.csv")

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