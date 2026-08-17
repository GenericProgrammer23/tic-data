from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, BinaryIO

try:
    import ijson as _ijson
except ModuleNotFoundError:  # pragma: no cover - production installs ijson
    _ijson = None

FALLBACK_MAX_BYTES = 32 * 1024 * 1024


def items(stream: BinaryIO, prefix: str) -> Iterator[Any]:
    if _ijson is not None:
        yield from _ijson.items(stream, prefix)
        return
    data = _fallback_load(stream)
    current: Any = data
    parts = prefix.split(".")
    if parts and parts[-1] == "item":
        parts = parts[:-1]
    for part in parts:
        if not isinstance(current, dict):
            return
        current = current.get(part)
    if isinstance(current, list):
        yield from current


def parse(stream: BinaryIO) -> Iterator[tuple[str, str, Any]]:
    if _ijson is not None:
        yield from _ijson.parse(stream)
        return
    data = _fallback_load(stream)
    if not isinstance(data, dict):
        return
    for key, value in data.items():
        if isinstance(value, list):
            yield key, "start_array", None
        elif isinstance(value, dict):
            yield key, "start_map", None
        elif value is None:
            yield key, "null", None
        elif isinstance(value, bool):
            yield key, "boolean", value
        elif isinstance(value, (int, float)):
            yield key, "number", value
        else:
            yield key, "string", value


def _fallback_load(stream: BinaryIO) -> Any:
    try:
        position = stream.tell()
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(position)
    except (AttributeError, OSError):
        size = 0
    if size > FALLBACK_MAX_BYTES:
        raise RuntimeError(
            "ijson is required for TiC files larger than 32 MiB. Install project dependencies first."
        )
    return json.load(stream)
