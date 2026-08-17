from pathlib import Path

SOURCE_FILE = Path("/app/source_data/olist_order_payments_dataset.csv")
ORDERS_FILE = Path("/app/simulated_data/orders.csv")
OUTPUT_FILE = Path("/app/simulated_data/payments.csv")

EXPECTED_COLUMNS = [
    "order_id",
    "payment_sequential",
    "payment_type",
    "payment_installments",
    "payment_value",
]

VALID_PAYMENT_TYPES = {
    "credit_card",
    "boleto",
    "voucher",
    "debit_card",
    "not_defined",
}