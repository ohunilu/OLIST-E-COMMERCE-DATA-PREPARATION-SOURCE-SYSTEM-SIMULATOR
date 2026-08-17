from pathlib import Path

SOURCE_FILE = Path("/app/source_data/olist_products_dataset.csv")
TRANSLATION_FILE = Path("/app/source_data/product_category_name_translation.csv")
OUTPUT_FILE = Path("/app/simulated_data/products.csv")

EXPECTED_SOURCE_COLUMNS = [
    "product_id",
    "product_category_name",
    "product_name_lenght",
    "product_description_lenght",
    "product_photos_qty",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
]

EXPECTED_TRANSLATION_COLUMNS = [
    "product_category_name",
    "product_category_name_english",
]

EXPECTED_OUTPUT_COLUMNS = [
    "product_id",
    "product_category_name",
    "product_name_lenght",
    "product_description_lenght",
    "product_photos_qty",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
]