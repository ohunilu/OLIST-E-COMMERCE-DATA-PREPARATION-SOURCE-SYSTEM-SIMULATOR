from __future__ import annotations

import pandas as pd

from customer_util.customer_synthetic import generate_synthetic_pii


def transform_customers(
    df: pd.DataFrame,
    *,
    country: str = "Brazil",
) -> pd.DataFrame:
    """
    Transform the raw Olist customer dataset into the simulated
    operational customer model.
    """
    output = pd.DataFrame()

    output["customer_id"] = (
        df["customer_id"]
        .astype("string")
        .str.strip()
    )

    output["customer_unique_id"] = (
        df["customer_unique_id"]
        .astype("string")
        .str.strip()
    )

    pii_records = [
        generate_synthetic_pii(customer_unique_id)
        for customer_unique_id in output["customer_unique_id"]
    ]

    pii_df = pd.DataFrame(pii_records)

    output = pd.concat(
        [output.reset_index(drop=True), pii_df],
        axis=1,
    )

    output["city"] = (
        df["customer_city"]
        .astype("string")
        .str.strip()
        .str.title()
    )

    output["state"] = (
        df["customer_state"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    output["zip_code_prefix"] = (
        df["customer_zip_code_prefix"]
        .astype("string")
        .str.zfill(5)
    )

    output["country"] = country

    output["signup_date"] = pd.NaT

    return output