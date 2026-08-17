from __future__ import annotations

from pathlib import Path
from typing import Any

from . import streaming

from .source import open_json_binary


def discover_in_network_files(
    path: Path,
    *,
    plan_name: str | None = None,
    issuer_name: str | None = None,
    plan_id: str | None = None,
    plan_sponsor_name: str | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with open_json_binary(path) as stream:
        for structure in streaming.items(stream, "reporting_structure.item"):
            matching_plans = [
                plan
                for plan in structure.get("reporting_plans", []) or []
                if _plan_matches(
                    plan,
                    plan_name=plan_name,
                    issuer_name=issuer_name,
                    plan_id=plan_id,
                    plan_sponsor_name=plan_sponsor_name,
                )
            ]
            if not matching_plans:
                continue
            for file_location in structure.get("in_network_files", []) or []:
                location = file_location.get("location")
                if location:
                    results.append(
                        {
                            "location": location,
                            "description": file_location.get("description"),
                            "matching_plans": matching_plans,
                        }
                    )
    return _dedupe_by_location(results)


def _plan_matches(
    plan: dict[str, Any],
    *,
    plan_name: str | None,
    issuer_name: str | None,
    plan_id: str | None,
    plan_sponsor_name: str | None,
) -> bool:
    filters = {
        "plan_name": plan_name,
        "issuer_name": issuer_name,
        "plan_id": plan_id,
        "plan_sponsor_name": plan_sponsor_name,
    }
    active = {field: value for field, value in filters.items() if value}
    if not active:
        return True
    for field, expected in active.items():
        actual = str(plan.get(field, ""))
        if field == "plan_id":
            if actual != str(expected):
                return False
        elif str(expected).casefold() not in actual.casefold():
            return False
    return True


def _dedupe_by_location(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_location: dict[str, dict[str, Any]] = {}
    for row in rows:
        location = row["location"]
        if location not in by_location:
            by_location[location] = row
        else:
            by_location[location]["matching_plans"].extend(row["matching_plans"])
    return list(by_location.values())
