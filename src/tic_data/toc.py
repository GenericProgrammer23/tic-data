from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

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
    """Return the raw plan-to-file mapping, deduplicated by canonical file URL."""
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
                            "canonical_location": canonical_location(location),
                            "description": file_location.get("description"),
                            "matching_plans": matching_plans,
                        }
                    )
    return _dedupe_by_location(results)


def catalog_in_network_files(
    path: Path,
    *,
    plan_name: str | None = None,
    issuer_name: str | None = None,
    plan_id: str | None = None,
    plan_sponsor_name: str | None = None,
) -> dict[str, Any]:
    """Build a compact user-facing catalog from a TiC Table-of-Contents file.

    Large payer indexes repeat the same MRF URL for thousands of employer plans.
    The catalog collapses those references into one row per actual rate file and
    summarizes which plan types/sponsors point to it.
    """
    metadata = _read_toc_metadata(path)
    by_file: dict[str, dict[str, Any]] = {}

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
                location = str(file_location.get("location") or "").strip()
                if not location:
                    continue
                canonical = canonical_location(location)
                description = str(file_location.get("description") or "").strip()
                key = canonical or location
                row = by_file.setdefault(
                    key,
                    {
                        "description": description,
                        "network": network_label(description),
                        "location": location,
                        "canonical_location": canonical,
                        "file_format": file_format(location),
                        "source": source_label(description, location),
                        "plan_names": set(),
                        "issuer_names": set(),
                        "plan_ids": set(),
                        "plan_sponsors": set(),
                        "reference_count": 0,
                    },
                )
                row["reference_count"] += 1
                for plan in matching_plans:
                    _add_if_present(row["plan_names"], plan.get("plan_name"))
                    _add_if_present(row["issuer_names"], plan.get("issuer_name"))
                    _add_if_present(row["plan_ids"], plan.get("plan_id"))
                    _add_if_present(row["plan_sponsors"], plan.get("plan_sponsor_name"))

    files: list[dict[str, Any]] = []
    for row in by_file.values():
        sponsors = sorted(row.pop("plan_sponsors"), key=str.casefold)
        row["plan_names"] = sorted(row["plan_names"], key=str.casefold)
        row["issuer_names"] = sorted(row["issuer_names"], key=str.casefold)
        row["plan_ids"] = sorted(row["plan_ids"], key=str.casefold)
        row["plan_sponsor_count"] = len(sponsors)
        row["sample_plan_sponsors"] = sponsors[:10]
        files.append(row)

    files.sort(
        key=lambda row: (
            0 if row["source"] == "Cigna" else 1,
            row["network"].casefold(),
            row["description"].casefold(),
        )
    )
    return {
        "metadata": metadata,
        "file_count": len(files),
        "files": files,
    }


def _read_toc_metadata(path: Path) -> dict[str, Any]:
    wanted = {
        "reporting_entity_name",
        "reporting_entity_type",
        "last_updated_on",
        "version",
    }
    metadata: dict[str, Any] = {}
    with open_json_binary(path) as stream:
        for prefix, event, value in streaming.parse(stream):
            if prefix in wanted and event in {"string", "number", "boolean", "null"}:
                metadata[prefix] = value
            if prefix == "reporting_structure" and event == "start_array":
                break
    return metadata


def canonical_location(location: str) -> str:
    """Strip signatures/query parameters so repeated signed URLs deduplicate."""
    parts = urlsplit(location)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def file_format(location: str) -> str:
    path = urlsplit(location).path.lower()
    if path.endswith(".json.gz") or path.endswith(".gz"):
        return "json.gz"
    if path.endswith(".zip"):
        return "zip"
    if path.endswith(".json"):
        return "json"
    return Path(path).suffix.lstrip(".") or "unknown"


def source_label(description: str, location: str) -> str:
    text = f"{description} {location}".casefold()
    if "cigna-health-life-insurance-company" in text or "cignahealthlife" in text:
        return "Cigna"
    return "Affiliate / shared network"


def network_label(description: str) -> str:
    text = description.strip()
    text = re.sub(r"^\d{4}[-_]\d{2}[-_]\d{2}[_-]", "", text)
    text = re.sub(
        r"^cigna-health-life-insurance-company[_-]",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"[_-]in[_-]network[_-]rates$", "", text, flags=re.IGNORECASE)
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return description or "Unlabeled network"
    acronyms = {"oap", "ppo", "hmo", "gppo", "mvp", "az", "ca", "ny"}
    words = [word.upper() if word.casefold() in acronyms else word.title() for word in text.split()]
    return " ".join(words)


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
            if _normalize_plan_id(actual) != _normalize_plan_id(str(expected)):
                return False
        elif str(expected).casefold() not in actual.casefold():
            return False
    return True


def _normalize_plan_id(value: str) -> str:
    return "".join(ch for ch in value if ch.isalnum()).casefold()


def _add_if_present(target: set[str], value: Any) -> None:
    if value is not None and str(value).strip():
        target.add(str(value).strip())


def _dedupe_by_location(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_location: dict[str, dict[str, Any]] = {}
    for row in rows:
        location = row["canonical_location"] or row["location"]
        if location not in by_location:
            by_location[location] = row
        else:
            by_location[location]["matching_plans"].extend(row["matching_plans"])
    return list(by_location.values())
