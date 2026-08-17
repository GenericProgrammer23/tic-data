from __future__ import annotations

import gzip
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator

import httpx


DEFAULT_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024 * 1024  # 100 GiB safety ceiling


@contextmanager
def local_source_from_url(
    url: str,
    *,
    max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    timeout_seconds: float = 120.0,
) -> Iterator[Path]:
    suffix = ".json.gz" if url.lower().split("?", 1)[0].endswith(".gz") else ".json"
    with tempfile.TemporaryDirectory(prefix="tic-data-") as directory:
        path = Path(directory) / f"source{suffix}"
        downloaded = 0
        with httpx.stream(
            "GET",
            url,
            follow_redirects=True,
            timeout=httpx.Timeout(timeout_seconds, connect=30.0),
            headers={"User-Agent": "tic-data/0.1"},
        ) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_bytes:
                raise ValueError(f"Remote file exceeds {max_bytes:,} byte safety limit")
            with path.open("wb") as target:
                for chunk in response.iter_bytes(1024 * 1024):
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        raise ValueError(f"Remote file exceeds {max_bytes:,} byte safety limit")
                    target.write(chunk)
        yield path


@contextmanager
def local_source_from_upload(fileobj: BinaryIO, filename: str | None = None) -> Iterator[Path]:
    suffix = ".json.gz" if (filename or "").lower().endswith(".gz") else ".json"
    with tempfile.TemporaryDirectory(prefix="tic-data-") as directory:
        path = Path(directory) / f"upload{suffix}"
        with path.open("wb") as target:
            shutil.copyfileobj(fileobj, target, length=1024 * 1024)
        yield path


@contextmanager
def open_json_binary(path: Path) -> Iterator[BinaryIO]:
    with path.open("rb") as raw:
        magic = raw.read(2)
        raw.seek(0)
        if path.name.lower().endswith(".gz") or magic == b"\x1f\x8b":
            with gzip.GzipFile(fileobj=raw, mode="rb") as stream:
                yield stream
        else:
            yield raw
