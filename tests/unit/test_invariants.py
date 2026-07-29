from __future__ import annotations

import pytest

from agentic_platform.invariants.checks import InvariantError, InvariantGuard


def test_protected_path_detection() -> None:
    with pytest.raises(InvariantError) as ei:
        InvariantGuard.reject_protected_edits(["prepare.py"], ["prepare.py"])
    assert ei.value.code == 1


def test_metric_improvement() -> None:
    assert InvariantGuard.require_metric_improvement("minimize", "strictly_better", 1.0, 0.9)
    assert not InvariantGuard.require_metric_improvement("minimize", "strictly_better", 1.0, 1.1)
    assert InvariantGuard.require_metric_improvement("maximize", "strictly_better", 1.0, 1.1)


def test_claim_requires_source() -> None:
    with pytest.raises(InvariantError) as ei:
        InvariantGuard.require_claim_source({"id": "c1", "type": "Claim", "provenance": {}})
    assert ei.value.code == 5
