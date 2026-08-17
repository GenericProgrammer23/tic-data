from __future__ import annotations

import csv
import io
from typing import Any


CSV_COLUMNS = [
    "billing_code_type",
    "billing_code",
    "name",
    "description",
    "negotiation_arrangement",
    "negotiated_type",
    "negotiated_rate",
    "billing_class",
    "setting",
    "service_code",
    "expiration_date",
    "billing_code_modifier",
    "provider_references",
    "additional_information",
]


def rates_to_csv(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        flattened = dict(row)
        for field in ("service_code", "billing_code_modifier", "provider_references"):
            flattened[field] = "|".join(str(v) for v in row.get(field, []) or [])
        writer.writerow(flattened)
    return output.getvalue()
