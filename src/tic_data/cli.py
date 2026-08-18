from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .export import rates_to_csv
from .models import OrganizationSelector, RateFilters
from .parser import extract_rates
from .source import local_source_from_url
from .toc import catalog_in_network_files, discover_in_network_files


def main() -> None:
    parser = argparse.ArgumentParser(prog="tic-data")
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract", help="Extract rates for one organization")
    source = extract.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path)
    source.add_argument("--url")
    extract.add_argument("--npi", action="append", default=[])
    extract.add_argument("--tin", action="append", default=[])
    extract.add_argument("--business-name", action="append", default=[])
    extract.add_argument("--code", action="append", default=[])
    extract.add_argument("--code-type", action="append", default=[])
    extract.add_argument("--service-code", action="append", default=[])
    extract.add_argument("--billing-class", action="append", default=[])
    extract.add_argument("--negotiated-type", action="append", default=[])
    extract.add_argument("--limit", type=int, default=5000)
    extract.add_argument("--format", choices=["json", "csv"], default="json")
    extract.add_argument("--output", type=Path)

    toc = sub.add_parser("toc", help="Find plan-linked in-network URLs in a TiC table-of-contents")
    _add_toc_args(toc)

    catalog = sub.add_parser("catalog", help="Build a deduplicated network/file catalog from a TiC index")
    _add_toc_args(catalog)

    args = parser.parse_args()
    if args.command == "extract":
        _extract(args)
    elif args.command == "catalog":
        _catalog(args)
    else:
        _toc(args)


def _add_toc_args(command: argparse.ArgumentParser) -> None:
    source = command.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path)
    source.add_argument("--url")
    command.add_argument("--plan-name")
    command.add_argument("--issuer-name")
    command.add_argument("--plan-id")
    command.add_argument("--plan-sponsor-name")


def _extract(args: argparse.Namespace) -> None:
    organization = OrganizationSelector(
        npis=args.npi,
        tins=args.tin,
        business_names=args.business_name,
    )
    filters = RateFilters(
        billing_codes=args.code,
        billing_code_types=args.code_type,
        service_codes=args.service_code,
        billing_classes=args.billing_class,
        negotiated_types=args.negotiated_type,
        limit=args.limit,
    )
    if args.url:
        with local_source_from_url(args.url) as path:
            result = extract_rates(path, organization, filters)
    else:
        result = extract_rates(args.file, organization, filters)

    if args.format == "csv":
        payload = rates_to_csv(result.rates)
    else:
        payload = json.dumps(
            {
                "metadata": result.metadata,
                "matched_provider_group_ids": sorted(result.matched_provider_group_ids, key=str),
                "matched_providers": [asdict(row) for row in result.matched_providers],
                "rate_count": len(result.rates),
                "truncated": result.truncated,
                "rates": result.rates,
            },
            indent=2,
            default=str,
        )
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)


def _toc_kwargs(args: argparse.Namespace) -> dict:
    return {
        "plan_name": args.plan_name,
        "issuer_name": args.issuer_name,
        "plan_id": args.plan_id,
        "plan_sponsor_name": args.plan_sponsor_name,
    }


def _run_source(args: argparse.Namespace, function):
    if args.url:
        with local_source_from_url(args.url) as path:
            return function(path, **_toc_kwargs(args))
    return function(args.file, **_toc_kwargs(args))


def _toc(args: argparse.Namespace) -> None:
    print(json.dumps(_run_source(args, discover_in_network_files), indent=2))


def _catalog(args: argparse.Namespace) -> None:
    print(json.dumps(_run_source(args, catalog_in_network_files), indent=2))
