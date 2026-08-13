from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from agentic_platform.core.paths import schemas_dir

SCHEMA_FILES = {
    "ControlDocument": "control-document.schema.json",
    "Trial": "trial.schema.json",
    "CommitNode": "commit-node.schema.json",
    "GraphUpdate": "graph-update.schema.json",
    "EvaluationResult": "evaluation-result.schema.json",
    "BudgetDeclaration": "budget-declaration.schema.json",
    "Run": "run.schema.json",
}


@lru_cache(maxsize=None)
def _load_schema(name: str) -> dict[str, Any]:
    path = schemas_dir() / SCHEMA_FILES[name]
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def validate_schema(name: str, document: dict[str, Any]) -> list[str]:
    """Return list of validation error messages (empty if valid)."""
    schema = _load_schema(name)
    validator = Draft202012Validator(schema)
    return sorted(e.message for e in validator.iter_errors(document))


def assert_valid(name: str, document: dict[str, Any]) -> None:
    errors = validate_schema(name, document)
    if errors:
        raise ValueError(f"{name} schema violation: " + "; ".join(errors))
