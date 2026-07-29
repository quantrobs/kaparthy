from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    env = os.environ.get("AGENTIC_ROOT")
    if env:
        return Path(env).resolve()
    # src/agentic_platform/core/paths.py -> repo root
    return Path(__file__).resolve().parents[3]


def contracts_dir() -> Path:
    return repo_root() / "contracts" / "v0.1.0"


def schemas_dir() -> Path:
    return contracts_dir() / "schemas"


def default_data_dir() -> Path:
    env = os.environ.get("AGENTIC_DATA")
    if env:
        return Path(env).resolve()
    return repo_root() / "data"
