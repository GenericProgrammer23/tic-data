from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .export import rates_to_csv
from .models import OrganizationSelector, RateFilters
from .parser import extract_rates
from .source import local_source_from_url
from .toc import discover_in_network_files


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

    toc = sub.add_parser("toc", help="Find in-network URLs in a TiC table-of-contents")
    toc_source = toc.add_mutually_exclusive_group(required=True)
    toc_source.add_argument("--file", type=Path)
    toc_source.add_argument("--url")
    toc.add_argument("--plan-name")
    toc.add_argument("--issuer-name")
    toc.add_argument("--plan-id")
    toc.add_argument("--plan-sponsor-name")

    args = parser.parse_args()
    if args.command == "extract":
        _extract(args)
    else:
        _toc(args)


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


def _toc(args: argparse.Namespace) -> None:
    def run(path: Path) -> list[dict]:
        return discover_in_network_files(
            path,
            plan_name=args.plan_name,
            issuer_name=args.issuer_name,
            plan_id=args.plan_id,
            plan_sponsor_name=args.plan_sponsor_name,
        )

    if args.url:
        with local_source_from_url(args.url) as path:
            rows = run(path)
    else:
        rows = run(args.file)
    print(json.dumps(rows, indent=2))
