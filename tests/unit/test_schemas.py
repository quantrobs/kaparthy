from __future__ import annotations

from agentic_platform.core.validation import validate_schema
from tests.conftest import make_control_payload


def test_control_document_schema_valid() -> None:
    doc = make_control_payload()
    doc["id"] = "ctl_test"
    doc["version"] = "1"
    doc["created_at"] = "2026-07-28T00:00:00Z"
    errors = validate_schema("ControlDocument", doc)
    assert errors == []


def test_control_document_schema_rejects_missing_metric() -> None:
    doc = make_control_payload()
    doc["id"] = "ctl_test"
    doc["version"] = "1"
    del doc["metric"]
    errors = validate_schema("ControlDocument", doc)
    assert errors


def test_control_document_accepts_keep_gate() -> None:
    doc = make_control_payload()
    doc["id"] = "ctl_test"
    doc["version"] = "1"
    doc["created_at"] = "2026-07-28T00:00:00Z"
    doc["keep_gate"] = {
        "mode": "paired_pace",
        "n_min": 3,
        "alpha": 0.2,
        "lambda": 0.8,
        "seeds": [7919],
    }
    errors = validate_schema("ControlDocument", doc)
    assert errors == []
