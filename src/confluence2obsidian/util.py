from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin


_INVALID_FILENAME = re.compile(r'[\\/:*?"<>|]')
_WHITESPACE = re.compile(r"\s+")


def safe_name(value: str, fallback: str = "Untitled") -> str:
    value = _INVALID_FILENAME.sub("-", value).strip().strip(".")
    value = _WHITESPACE.sub(" ", value)
    return value[:180] or fallback


def ensure_within(root: Path, path: Path) -> Path:
    root = root.resolve()
    resolved = path.resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError(f"Refusing to write outside vault: {resolved}")
    return resolved


def absolute_url(base_url: str, link: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", link)
