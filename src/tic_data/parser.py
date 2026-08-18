from __future__ import annotations

from collections.abc import Callable, Iterable
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

ProgressCallback = Callable[[float, str, str, dict[str, Any]], None]


def _notify(
    callback: ProgressCallback | None,
    percent: float,
    stage: str,
    message: str,
    **details: Any,
) -> None:
    if callback:
        callback(percent, stage, message, details)


def extract_rates(
    path: Path,
    organization: OrganizationSelector,
    filters: RateFilters | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ExtractionResult:
    filters = filters or RateFilters()

    _notify(progress_callback, 47, "Reading metadata", "Reading rate-file metadata…")
    metadata = _read_metadata(path)

    _notify(
        progress_callback,
        52,
        "Finding provider groups",
        "Scanning provider groups for the entered TIN/NPI…",
    )
    group_ids, providers, provider_diagnostics = _find_provider_matches(
        path,
        organization,
        progress_callback,
    )

    _notify(
        progress_callback,
        70,
        "Finding negotiated rates",
        f"Provider scan complete. {len(group_ids)} provider group ID(s) matched. Scanning requested codes and negotiated rates…",
        matched_provider_group_ids=sorted(group_ids, key=str),
        matched_provider_group_id_count=len(group_ids),
    )
    rates, truncated, rate_diagnostics = _find_rates(
        path,
        organization,
        group_ids,
        filters,
        progress_callback,
    )

    diagnostics = {
        "normalized_organization": {
            "tins": list(organization.tins),
            "npis": list(organization.npis),
            "business_names": list(organization.business_names),
        },
        "requested_filters": {
            "billing_codes": list(filters.billing_codes),
            "billing_code_types": list(filters.billing_code_types),
            "billing_classes": list(filters.billing_classes),
            "service_codes": list(filters.service_codes),
            "negotiated_types": list(filters.negotiated_types),
        },
        **provider_diagnostics,
        **rate_diagnostics,
    }

    _notify(
        progress_callback,
        100,
        "Complete",
        f"Complete. Found {len(rates)} negotiated rate row(s).",
        rate_count=len(rates),
        matched_provider_group_id_count=len(group_ids),
    )

    return ExtractionResult(
        metadata=metadata,
        matched_provider_group_ids=group_ids,
        matched_providers=providers,
        rates=rates,
        truncated=truncated,
        diagnostics=diagnostics,
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
    path: Path,
    organization: OrganizationSelector,
    progress_callback: ProgressCallback | None = None,
) -> tuple[set[int | str], list[ProviderMatch], dict[str, Any]]:
    group_ids: set[int | str] = set()
    providers: list[ProviderMatch] = []
    references_scanned = 0
    groups_scanned = 0
    groups_matched = 0

    with open_json_binary(path) as stream:
        for reference in streaming.items(stream, "provider_references.item"):
            references_scanned += 1
            provider_group_id = reference.get("provider_group_id")
            network_names = tuple(str(v) for v in reference.get("network_name", []) if v is not None)

            for group in reference.get("provider_groups", []) or []:
                groups_scanned += 1
                if _provider_group_matches(group, organization):
                    groups_matched += 1
                    if provider_group_id is not None:
                        group_ids.add(provider_group_id)
                    providers.extend(_provider_match_rows(group, provider_group_id, network_names))

            if references_scanned % 5000 == 0:
                _notify(
                    progress_callback,
                    60,
                    "Finding provider groups",
                    f"Scanned {references_scanned:,} provider references / {groups_scanned:,} provider groups; {groups_matched:,} matching group(s) found so far…",
                    provider_references_scanned=references_scanned,
                    provider_groups_scanned=groups_scanned,
                    provider_groups_matched=groups_matched,
                    matched_provider_group_ids=sorted(group_ids, key=str),
                )

    return group_ids, providers, {
        "provider_references_scanned": references_scanned,
        "provider_groups_scanned": groups_scanned,
        "provider_groups_matched": groups_matched,
        "matched_provider_group_id_count": len(group_ids),
        "matched_provider_group_ids": sorted(group_ids, key=str),
    }


def _provider_group_matches(group: dict[str, Any], selector: OrganizationSelector) -> bool:
    wanted_npis = {normalize_id(v) for v in selector.npis}
    wanted_tins = {normalize_id(v) for v in selector.tins}
    wanted_names = {v.casefold() for v in selector.business_names}

    group_npis = {normalize_id(v) for v in group.get("npi", []) or []}
    tin = group.get("tin") or {}
    tin_type = str(tin.get("type") or "").strip().casefold()
    tin_value = normalize_id(tin.get("value"))
    business_name = str(tin.get("business_name") or "").strip().casefold()

    # For a TIN/EIN search, treat an explicit EIN as the expected TiC identifier.
    # Some payer files omit tin.type, so an empty type is accepted as a fallback.
    tin_match = bool(
        wanted_tins
        and tin_value in wanted_tins
        and tin_type in {"", "ein"}
    )

    return bool(
        (wanted_npis and wanted_npis.intersection(group_npis))
        or tin_match
        or (wanted_names and any(name in business_name for name in wanted_names))
    )


def _normalize_group_id(value: Any) -> str:
    """Normalize provider-group references across JSON number/string representations."""
    if value is None:
        return ""
    return str(value).strip().casefold()


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
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[dict[str, Any]], bool, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    truncated = False
    requested_codes = {str(v) for v in filters.billing_codes}
    requested_codes_seen: set[str] = set()
    code_types_seen_for_requested_codes: set[str] = set()
    billing_classes_seen_for_linked_rates: set[str] = set()
    negotiated_types_seen_for_linked_rates: set[str] = set()

    normalized_matched_group_ids = {
        _normalize_group_id(value)
        for value in matched_group_ids
        if _normalize_group_id(value)
    }

    in_network_items_scanned = 0
    service_items_matched_filters = 0
    negotiated_rate_groups_scanned = 0
    negotiated_rate_groups_linked = 0
    embedded_provider_groups_matched = 0
    negotiated_prices_scanned_for_linked_groups = 0
    negotiated_prices_matched_filters = 0

    with open_json_binary(path) as stream:
        for item in streaming.items(stream, "in_network.item"):
            in_network_items_scanned += 1
            billing_code = str(item.get("billing_code", ""))
            billing_code_type = str(item.get("billing_code_type", ""))

            if requested_codes and billing_code in requested_codes:
                requested_codes_seen.add(billing_code)
                if billing_code_type:
                    code_types_seen_for_requested_codes.add(billing_code_type)

            if not _service_matches(item, filters):
                if in_network_items_scanned % 500 == 0:
                    _notify(
                        progress_callback,
                        82,
                        "Finding negotiated rates",
                        f"Scanned {in_network_items_scanned:,} in-network service rows; requested codes seen: {', '.join(sorted(requested_codes_seen)) or 'none yet'}…",
                        in_network_items_scanned=in_network_items_scanned,
                        requested_billing_codes_seen=sorted(requested_codes_seen),
                        negotiated_rate_groups_linked_to_provider=negotiated_rate_groups_linked,
                        rate_count=len(rows),
                    )
                continue

            service_items_matched_filters += 1

            for negotiated in item.get("negotiated_rates", []) or []:
                negotiated_rate_groups_scanned += 1
                refs = set(negotiated.get("provider_references", []) or [])
                normalized_refs = {
                    _normalize_group_id(value)
                    for value in refs
                    if _normalize_group_id(value)
                }
                embedded_groups = negotiated.get("provider_groups", []) or []

                # Normalize both sides so JSON number 847392 and string "847392"
                # resolve to the same provider group.
                ref_match = bool(normalized_matched_group_ids.intersection(normalized_refs))
                embedded_matches = [
                    group for group in embedded_groups if _provider_group_matches(group, organization)
                ]
                embedded_provider_groups_matched += len(embedded_matches)

                if not (ref_match or embedded_matches):
                    continue

                negotiated_rate_groups_linked += 1
                for price in negotiated.get("negotiated_prices", []) or []:
                    negotiated_prices_scanned_for_linked_groups += 1
                    billing_class = str(price.get("billing_class", "")).strip()
                    negotiated_type = str(price.get("negotiated_type", "")).strip()
                    if billing_class:
                        billing_classes_seen_for_linked_rates.add(billing_class)
                    if negotiated_type:
                        negotiated_types_seen_for_linked_rates.add(negotiated_type)
                    if not _price_matches(price, filters):
                        continue

                    negotiated_prices_matched_filters += 1
                    row = _rate_row(item, price, refs if ref_match else set(), embedded_matches)
                    rows.append(row)

                    if filters.limit is not None and len(rows) >= filters.limit:
                        truncated = True
                        return rows, truncated, _rate_diagnostics(
                            requested_codes_seen,
                            code_types_seen_for_requested_codes,
                            billing_classes_seen_for_linked_rates,
                            negotiated_types_seen_for_linked_rates,
                            in_network_items_scanned,
                            service_items_matched_filters,
                            negotiated_rate_groups_scanned,
                            negotiated_rate_groups_linked,
                            embedded_provider_groups_matched,
                            negotiated_prices_scanned_for_linked_groups,
                            negotiated_prices_matched_filters,
                        )

            if in_network_items_scanned % 500 == 0:
                _notify(
                    progress_callback,
                    86,
                    "Finding negotiated rates",
                    f"Scanned {in_network_items_scanned:,} in-network service rows; {negotiated_rate_groups_linked:,} rate group(s) linked to the provider; {len(rows):,} price row(s) found…",
                    in_network_items_scanned=in_network_items_scanned,
                    requested_billing_codes_seen=sorted(requested_codes_seen),
                    negotiated_rate_groups_linked_to_provider=negotiated_rate_groups_linked,
                    negotiated_prices_matched_filters=negotiated_prices_matched_filters,
                    rate_count=len(rows),
                )

    return rows, truncated, _rate_diagnostics(
        requested_codes_seen,
        code_types_seen_for_requested_codes,
        billing_classes_seen_for_linked_rates,
        negotiated_types_seen_for_linked_rates,
        in_network_items_scanned,
        service_items_matched_filters,
        negotiated_rate_groups_scanned,
        negotiated_rate_groups_linked,
        embedded_provider_groups_matched,
        negotiated_prices_scanned_for_linked_groups,
        negotiated_prices_matched_filters,
    )


def _rate_diagnostics(
    requested_codes_seen: set[str],
    code_types_seen_for_requested_codes: set[str],
    billing_classes_seen_for_linked_rates: set[str],
    negotiated_types_seen_for_linked_rates: set[str],
    in_network_items_scanned: int,
    service_items_matched_filters: int,
    negotiated_rate_groups_scanned: int,
    negotiated_rate_groups_linked: int,
    embedded_provider_groups_matched: int,
    negotiated_prices_scanned_for_linked_groups: int,
    negotiated_prices_matched_filters: int,
) -> dict[str, Any]:
    return {
        "in_network_items_scanned": in_network_items_scanned,
        "requested_billing_codes_seen": sorted(requested_codes_seen),
        "billing_code_types_seen_for_requested_codes": sorted(code_types_seen_for_requested_codes),
        "service_items_matched_filters": service_items_matched_filters,
        "negotiated_rate_groups_scanned": negotiated_rate_groups_scanned,
        "negotiated_rate_groups_linked_to_provider": negotiated_rate_groups_linked,
        "embedded_provider_groups_matched": embedded_provider_groups_matched,
        "negotiated_prices_scanned_for_linked_groups": negotiated_prices_scanned_for_linked_groups,
        "negotiated_prices_matched_filters": negotiated_prices_matched_filters,
        "billing_classes_seen_for_linked_rates": sorted(billing_classes_seen_for_linked_rates),
        "negotiated_types_seen_for_linked_rates": sorted(negotiated_types_seen_for_linked_rates),
    }


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
