from __future__ import annotations

import json
from dataclasses import asdict
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from .export import rates_to_csv
from .models import OrganizationSelector, RateFilters, TocRequest, UrlExtractionRequest
from .parser import extract_rates
from .source import local_source_from_upload, local_source_from_url
from .toc import discover_in_network_files

app = FastAPI(
    title="TIC data",
    version="0.1.0",
    description="Stream and filter Transparency in Coverage machine-readable files.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/extract/url")
def extract_from_url(request: UrlExtractionRequest) -> dict:
    try:
        with local_source_from_url(str(request.url)) as path:
            return _result_payload(extract_rates(path, request.organization, request.filters))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/extract/upload")
def extract_from_upload(
    file: Annotated[UploadFile, File(...)],
    organization_json: Annotated[str, Form(...)],
    filters_json: Annotated[str, Form()] = "{}",
) -> dict:
    try:
        organization = OrganizationSelector.model_validate(json.loads(organization_json))
        filters = RateFilters.model_validate(json.loads(filters_json))
        with local_source_from_upload(file.file, file.filename) as path:
            return _result_payload(extract_rates(path, organization, filters))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/extract/url.csv", response_class=PlainTextResponse)
def extract_from_url_csv(request: UrlExtractionRequest) -> PlainTextResponse:
    try:
        with local_source_from_url(str(request.url)) as path:
            result = extract_rates(path, request.organization, request.filters)
        return PlainTextResponse(
            rates_to_csv(result.rates),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="tic-rates.csv"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/toc/url")
def toc_from_url(request: TocRequest) -> dict:
    try:
        with local_source_from_url(str(request.url)) as path:
            files = discover_in_network_files(
                path,
                plan_name=request.plan_name,
                issuer_name=request.issuer_name,
                plan_id=request.plan_id,
                plan_sponsor_name=request.plan_sponsor_name,
            )
        return {"count": len(files), "in_network_files": files}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _result_payload(result) -> dict:
    return {
        "metadata": result.metadata,
        "matched_provider_group_ids": sorted(result.matched_provider_group_ids, key=str),
        "matched_providers": [asdict(row) for row in result.matched_providers],
        "rate_count": len(result.rates),
        "truncated": result.truncated,
        "rates": result.rates,
    }
