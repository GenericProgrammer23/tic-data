from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from . import streaming

from .models import (
    ExtractionResult,
    OrganizationSelector,
    ProviderMatch,
    RateFilters,
    normalize_id,
)
from .source import open_json_binary


ROOT_METADATA_FIELDS = (
    "reporting_entity_name",
    "reporting_entity_type",
    "issuer_name",
    "plan_name",
    "plan_id_type",
    "plan_id",
    "plan_sponsor_name",
    "plan_market_type",
    "last_updated_on",
    "version",
)


def extract_rates(
    path: Path,
    organization: OrganizationSelector,
    filters: RateFilters | None = None,
) -> ExtractionResult:
    filters = filters or RateFilters()
    metadata = _read_metadata(path)
    group_ids, providers = _find_provider_matches(path, organization)
    rates, truncated = _find_rates(path, organization, group_ids, filters)
    return ExtractionResult(
        metadata=metadata,
        matched_provider_group_ids=group_ids,
        matched_providers=providers,
        rates=rates,
        truncated=truncated,
    )


def _read_metadata(path: Path) -> dict[str, Any]:
    wanted = set(ROOT_METADATA_FIELDS)
    metadata: dict[str, Any] = {}
    with open_json_binary(path) as stream:
        for prefix, event, value in streaming.parse(stream):
            if prefix in wanted and event in {"string", "number", "boolean", "null"}:
                metadata[prefix] = value
                if len(metadata) == len(wanted):
                    break
            if prefix in {"in_network", "provider_references", "reporting_structure"} and event == "start_array":
                break
    return metadata


def _find_provider_matches(
    path: Path, organization: OrganizationSelector
) -> tuple[set[int | str], list[ProviderMatch]]:
    group_ids: set[int | str] = set()
    providers: list[ProviderMatch] = []
    with open_json_binary(path) as stream:
        for reference in streaming.items(stream, "provider_references.item"):
            provider_group_id = reference.get("provider_group_id")
            network_names = tuple(str(v) for v in reference.get("network_name", []) if v is not None)
            for group in reference.get("provider_groups", []) or []:
                if _provider_group_matches(group, organization):
                    if provider_group_id is not None:
                        group_ids.add(provider_group_id)
                    providers.extend(
                        _provider_match_rows(group, provider_group_id, network_names)
                    )
    return group_ids, providers


def _provider_group_matches(group: dict[str, Any], selector: OrganizationSelector) -> bool:
    wanted_npis = {normalize_id(v) for v in selector.npis}
    wanted_tins = {normalize_id(v) for v in selector.tins}
    wanted_names = {v.casefold() for v in selector.business_names}

    group_npis = {normalize_id(v) for v in group.get("npi", []) or []}
    tin = group.get("tin") or {}
    tin_value = normalize_id(tin.get("value"))
    business_name = str(tin.get("business_name") or "").strip().casefold()

    return bool(
        (wanted_npis and wanted_npis.intersection(group_npis))
        or (wanted_tins and tin_value in wanted_tins)
        or (wanted_names and any(name in business_name for name in wanted_names))
    )


def _provider_match_rows(
    group: dict[str, Any],
    provider_group_id: int | str | None,
    network_names: tuple[str, ...],
) -> list[ProviderMatch]:
    tin = group.get("tin") or {}
    npis = group.get("npi", []) or [None]
    return [
        ProviderMatch(
            provider_group_id=provider_group_id,
            npi=str(npi) if npi is not None else None,
            tin_type=str(tin.get("type")) if tin.get("type") is not None else None,
            tin_value=str(tin.get("value")) if tin.get("value") is not None else None,
            business_name=str(tin.get("business_name")) if tin.get("business_name") is not None else None,
            network_names=network_names,
        )
        for npi in npis
    ]


def _find_rates(
    path: Path,
    organization: OrganizationSelector,
    matched_group_ids: set[int | str],
    filters: RateFilters,
) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    truncated = False
    with open_json_binary(path) as stream:
        for item in streaming.items(stream, "in_network.item"):
            if not _service_matches(item, filters):
                continue
            for negotiated in item.get("negotiated_rates", []) or []:
                refs = set(negotiated.get("provider_references", []) or [])
                embedded_groups = negotiated.get("provider_groups", []) or []
                ref_match = bool(matched_group_ids.intersection(refs))
                embedded_matches = [
                    group for group in embedded_groups if _provider_group_matches(group, organization)
                ]
                if not (ref_match or embedded_matches):
                    continue
                for price in negotiated.get("negotiated_prices", []) or []:
                    if not _price_matches(price, filters):
                        continue
                    row = _rate_row(item, price, refs if ref_match else set(), embedded_matches)
                    rows.append(row)
                    if filters.limit is not None and len(rows) >= filters.limit:
                        truncated = True
                        return rows, truncated
    return rows, truncated


def _service_matches(item: dict[str, Any], filters: RateFilters) -> bool:
    if filters.billing_codes and str(item.get("billing_code")) not in set(filters.billing_codes):
        return False
    if filters.billing_code_types:
        allowed = {v.casefold() for v in filters.billing_code_types}
        if str(item.get("billing_code_type", "")).casefold() not in allowed:
            return False
    return True


def _price_matches(price: dict[str, Any], filters: RateFilters) -> bool:
    if filters.billing_classes:
        allowed = {v.casefold() for v in filters.billing_classes}
        if str(price.get("billing_class", "")).casefold() not in allowed:
            return False
    if filters.negotiated_types:
        allowed = {v.casefold() for v in filters.negotiated_types}
        if str(price.get("negotiated_type", "")).casefold() not in allowed:
            return False
    if filters.service_codes:
        wanted = set(filters.service_codes)
        actual = {str(v) for v in price.get("service_code", []) or []}
        if not wanted.intersection(actual):
            return False
    return True


def _rate_row(
    item: dict[str, Any],
    price: dict[str, Any],
    refs: Iterable[int | str],
    embedded_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    embedded = []
    for group in embedded_groups:
        tin = group.get("tin") or {}
        embedded.append(
            {
                "npis": [str(v) for v in group.get("npi", []) or []],
                "tin_type": tin.get("type"),
                "tin_value": tin.get("value"),
                "business_name": tin.get("business_name"),
            }
        )
    return {
        "negotiation_arrangement": item.get("negotiation_arrangement"),
        "name": item.get("name"),
        "description": item.get("description"),
        "billing_code_type": item.get("billing_code_type"),
        "billing_code_type_version": item.get("billing_code_type_version"),
        "billing_code": item.get("billing_code"),
        "negotiated_type": price.get("negotiated_type"),
        "negotiated_rate": price.get("negotiated_rate"),
        "expiration_date": price.get("expiration_date"),
        "service_code": price.get("service_code", []),
        "billing_class": price.get("billing_class"),
        "setting": price.get("setting"),
        "billing_code_modifier": price.get("billing_code_modifier", []),
        "additional_information": price.get("additional_information"),
        "provider_references": sorted(refs, key=str),
        "embedded_provider_matches": embedded,
    }
