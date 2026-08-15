from __future__ import annotations

import hashlib

from faker import Faker


def deterministic_seed(value: str) -> int:
    """
    Generate a stable integer seed from a customer identifier.

    The same customer identifier will always produce the same seed,
    ensuring deterministic synthetic PII across pipeline executions.
    """
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def generate_synthetic_pii(customer_unique_id: str) -> dict[str, str]:
    """
    Generate deterministic synthetic customer PII.

    The generated email uses the reserved .test domain so that it cannot
    accidentally represent a real production email address.
    """
    fake = Faker("pt_BR")
    fake.seed_instance(deterministic_seed(customer_unique_id))

    first_name = fake.first_name()
    last_name = fake.last_name()

    first_normalized = first_name.lower().replace(" ", ".")
    last_normalized = last_name.lower().replace(" ", ".")

    email = (
        f"{first_normalized}.{last_normalized}."
        f"{customer_unique_id[:8]}@example.test"
    )

    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": fake.phone_number(),
        "address_line_1": fake.street_address(),
    }