from __future__ import annotations

import gzip
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator
from urllib.parse import urlsplit

import httpx


DEFAULT_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024 * 1024  # 100 GiB safety ceiling
DownloadProgressCallback = Callable[[int, int | None], None]


def _source_suffix(name: str | None) -> str:
    clean = urlsplit(name or "").path.lower()
    if clean.endswith(".json.gz") or clean.endswith(".gz"):
        return ".json.gz"
    if clean.endswith(".zip"):
        return ".zip"
    return ".json"


@contextmanager
def local_source_from_url(
    url: str,
    *,
    max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    timeout_seconds: float = 120.0,
    progress_callback: DownloadProgressCallback | None = None,
) -> Iterator[Path]:
    suffix = _source_suffix(url)
    with tempfile.TemporaryDirectory(prefix="tic-data-") as directory:
        path = Path(directory) / f"source{suffix}"
        downloaded = 0
        with httpx.stream(
            "GET",
            url,
            follow_redirects=True,
            timeout=httpx.Timeout(timeout_seconds, connect=30.0),
            headers={"User-Agent": "tic-data/0.2"},
        ) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            total_bytes = int(content_length) if content_length and content_length.isdigit() else None
            if total_bytes and total_bytes > max_bytes:
                raise ValueError(f"Remote file exceeds {max_bytes:,} byte safety limit")
            if progress_callback:
                progress_callback(0, total_bytes)
            with path.open("wb") as target:
                for chunk in response.iter_bytes(1024 * 1024):
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        raise ValueError(f"Remote file exceeds {max_bytes:,} byte safety limit")
                    target.write(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_bytes)
        yield path


@contextmanager
def local_source_from_upload(fileobj: BinaryIO, filename: str | None = None) -> Iterator[Path]:
    suffix = _source_suffix(filename)
    with tempfile.TemporaryDirectory(prefix="tic-data-") as directory:
        path = Path(directory) / f"upload{suffix}"
        with path.open("wb") as target:
            shutil.copyfileobj(fileobj, target, length=1024 * 1024)
        yield path


def _zip_member(archive: zipfile.ZipFile) -> zipfile.ZipInfo:
    files = [item for item in archive.infolist() if not item.is_dir()]
    json_files = [
        item
        for item in files
        if item.filename.lower().endswith((".json", ".json.gz", ".gz"))
    ]
    candidates = json_files or files
    if not candidates:
        raise ValueError("ZIP archive does not contain a readable file")
    return max(candidates, key=lambda item: item.file_size)


@contextmanager
def open_json_binary(path: Path) -> Iterator[BinaryIO]:
    with path.open("rb") as raw:
        magic = raw.read(4)
        raw.seek(0)
        if path.name.lower().endswith(".zip") or magic.startswith(b"PK\x03\x04"):
            with zipfile.ZipFile(raw) as archive:
                member = _zip_member(archive)
                with archive.open(member, "r") as member_stream:
                    member_magic = member_stream.read(2)
                    member_stream.seek(0)
                    if member.filename.lower().endswith(".gz") or member_magic == b"\x1f\x8b":
                        with gzip.GzipFile(fileobj=member_stream, mode="rb") as stream:
                            yield stream
                    else:
                        yield member_stream
        elif path.name.lower().endswith(".gz") or magic[:2] == b"\x1f\x8b":
            with gzip.GzipFile(fileobj=raw, mode="rb") as stream:
                yield stream
        else:
            yield raw
