from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse

from .export import rates_to_csv
from .models import OrganizationSelector, RateFilters, TocRequest, UrlExtractionRequest
from .parser import extract_rates
from .source import local_source_from_upload, local_source_from_url
from .toc import catalog_in_network_files, discover_in_network_files
from .web import HTML_PAGE

app = FastAPI(
    title="TIC data",
    version="0.3.0",
    description="Map, stream, and filter Transparency in Coverage machine-readable files.",
)

_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()
_MAX_JOBS = 50


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(HTML_PAGE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/extract/jobs")
def create_extract_job(request: UrlExtractionRequest) -> dict[str, str]:
    job_id = uuid.uuid4().hex
    now = time.time()
    state = {
        "job_id": job_id,
        "status": "queued",
        "step": 0,
        "step_count": 4,
        "stage": "Queued",
        "message": "Search queued…",
        "percent": 0.0,
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "downloaded_bytes": 0,
        "total_bytes": None,
        "download_speed_bytes_per_second": None,
        "download_eta_seconds": None,
        "details": {},
        "result": None,
        "error": None,
        "_started_monotonic": None,
        "_download_started_monotonic": None,
    }
    with _JOBS_LOCK:
        _prune_jobs_locked()
        _JOBS[job_id] = state

    threading.Thread(
        target=_run_extract_job,
        args=(job_id, request),
        name=f"tic-extract-{job_id[:8]}",
        daemon=True,
    ).start()
    return {"job_id": job_id}


@app.get("/extract/jobs/{job_id}")
def get_extract_job(job_id: str) -> dict:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Extraction job not found")
        payload = {key: value for key, value in job.items() if not key.startswith("_")}
        started_monotonic = job.get("_started_monotonic")

    if started_monotonic is not None:
        payload["elapsed_seconds"] = max(0.0, time.monotonic() - started_monotonic)
    else:
        payload["elapsed_seconds"] = 0.0
    return payload


@app.post("/extract/url")
def extract_from_url(request: UrlExtractionRequest) -> dict:
    """Synchronous compatibility endpoint. The browser uses /extract/jobs."""
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


@app.post("/catalog/url")
def catalog_from_url(request: TocRequest) -> dict:
    try:
        with local_source_from_url(str(request.url)) as path:
            return catalog_in_network_files(
                path,
                plan_name=request.plan_name,
                issuer_name=request.issuer_name,
                plan_id=request.plan_id,
                plan_sponsor_name=request.plan_sponsor_name,
            )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/catalog/upload")
def catalog_from_upload(
    file: Annotated[UploadFile, File(...)],
    plan_name: Annotated[str, Form()] = "",
    issuer_name: Annotated[str, Form()] = "",
    plan_id: Annotated[str, Form()] = "",
    plan_sponsor_name: Annotated[str, Form()] = "",
) -> dict:
    try:
        with local_source_from_upload(file.file, file.filename) as path:
            return catalog_in_network_files(
                path,
                plan_name=plan_name or None,
                issuer_name=issuer_name or None,
                plan_id=plan_id or None,
                plan_sponsor_name=plan_sponsor_name or None,
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


def _run_extract_job(job_id: str, request: UrlExtractionRequest) -> None:
    started_monotonic = time.monotonic()
    _update_job(
        job_id,
        status="running",
        step=1,
        stage="Downloading rate file",
        message="Connecting to the payer and starting the rate-file download…",
        percent=2.0,
        started_at=time.time(),
        _started_monotonic=started_monotonic,
        _download_started_monotonic=time.monotonic(),
    )

    def download_progress(downloaded: int, total: int | None) -> None:
        with _JOBS_LOCK:
            job = _JOBS.get(job_id) or {}
            download_started = job.get("_download_started_monotonic") or time.monotonic()
        elapsed = max(time.monotonic() - download_started, 0.001)
        speed = downloaded / elapsed if downloaded else None
        eta = None
        if speed and total and downloaded < total:
            eta = max(0.0, (total - downloaded) / speed)
        if total:
            fraction = min(max(downloaded / total, 0.0), 1.0)
            percent = 2.0 + (43.0 * fraction)
            message = (
                f"Downloading rate file: {_format_bytes(downloaded)} / {_format_bytes(total)} "
                f"({fraction * 100:.1f}%)"
            )
        else:
            percent = 12.0
            message = f"Downloading rate file: {_format_bytes(downloaded)} downloaded…"

        _update_job(
            job_id,
            step=1,
            stage="Downloading rate file",
            message=message,
            percent=percent,
            downloaded_bytes=downloaded,
            total_bytes=total,
            download_speed_bytes_per_second=speed,
            download_eta_seconds=eta,
        )

    def parser_progress(
        percent: float,
        stage: str,
        message: str,
        details: dict[str, Any],
    ) -> None:
        step = 2 if percent < 70 else 3 if percent < 100 else 4
        _update_job(
            job_id,
            step=step,
            stage=stage,
            message=message,
            percent=percent,
            details=details,
            download_eta_seconds=None,
        )

    try:
        with local_source_from_url(
            str(request.url),
            progress_callback=download_progress,
        ) as path:
            _update_job(
                job_id,
                step=2,
                stage="Finding provider groups",
                message="Download complete. Reading the file and locating provider groups for the entered TIN/NPI…",
                percent=47.0,
                download_eta_seconds=None,
            )
            result = extract_rates(
                path,
                request.organization,
                request.filters,
                progress_callback=parser_progress,
            )

        payload = _result_payload(result)
        _update_job(
            job_id,
            status="complete",
            step=4,
            stage="Complete",
            message=f"Complete. Found {payload['rate_count']} negotiated rate row(s).",
            percent=100.0,
            completed_at=time.time(),
            result=payload,
            details=payload.get("diagnostics", {}),
            download_eta_seconds=None,
        )
    except Exception as exc:
        _update_job(
            job_id,
            status="error",
            stage="Error",
            message=str(exc),
            error=str(exc),
            completed_at=time.time(),
            download_eta_seconds=None,
        )


def _update_job(job_id: str, **values: Any) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return
        details = values.pop("details", None)
        if details is not None:
            merged_details = dict(job.get("details") or {})
            merged_details.update(details)
            job["details"] = merged_details
        job.update(values)


def _prune_jobs_locked() -> None:
    if len(_JOBS) < _MAX_JOBS:
        return
    ordered = sorted(
        _JOBS.items(),
        key=lambda pair: pair[1].get("created_at", 0),
    )
    for job_id, state in ordered:
        if len(_JOBS) < _MAX_JOBS:
            break
        if state.get("status") in {"complete", "error"}:
            _JOBS.pop(job_id, None)


def _format_bytes(value: int | float | None) -> str:
    if value is None:
        return "unknown"
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{amount:.0f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TB"


def _result_payload(result) -> dict:
    return {
        "metadata": result.metadata,
        "matched_provider_group_ids": sorted(result.matched_provider_group_ids, key=str),
        "matched_providers": [asdict(row) for row in result.matched_providers],
        "rate_count": len(result.rates),
        "truncated": result.truncated,
        "diagnostics": result.diagnostics,
        "rates": result.rates,
    }
