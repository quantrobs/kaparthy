from __future__ import annotations

import re
from typing import Iterable

# High-signal secret patterns — reject before commit / before keep
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("generic_api_key", re.compile(r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("github_pat", re.compile(r"ghp_[A-Za-z0-9]{36,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("jwt_like", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]


def find_secrets(text: str) -> list[str]:
    hits: list[str] = []
    for name, pat in SECRET_PATTERNS:
        if pat.search(text):
            hits.append(name)
    return hits


def scan_paths(files: Iterable[tuple[str, str]]) -> list[str]:
    """files: iterable of (path, content). Returns list of 'path:pattern' hits."""
    out: list[str] = []
    for path, content in files:
        for name in find_secrets(content):
            out.append(f"{path}:{name}")
    return out
