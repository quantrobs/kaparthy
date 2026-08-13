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


def test_metric_override_blocked() -> None:
    with pytest.raises(InvariantError) as ei:
        InvariantGuard.reject_metric_override_for_keep(0.1)
    assert ei.value.code == 2


def test_mutable_allowlist() -> None:
    with pytest.raises(InvariantError):
        InvariantGuard.reject_outside_mutable(["other.py"], ["train.py"])
    InvariantGuard.reject_outside_mutable(["train.py"], ["train.py"])


def test_oversized_diff() -> None:
    with pytest.raises(InvariantError):
        InvariantGuard.reject_oversized_diff(["a"] * 50, 10)
    with pytest.raises(InvariantError):
        InvariantGuard.reject_oversized_diff(["a"], InvariantGuard.MAX_DIFF_BYTES + 1)


def test_holdout_authorship_blocked() -> None:
    with pytest.raises(InvariantError) as ei:
        InvariantGuard.reject_holdout_authorship(["keep_gate.json"])
    assert ei.value.code == 2


def test_sealed_keep_requires_certificate() -> None:
    with pytest.raises(InvariantError) as ei:
        InvariantGuard.require_sealed_keep(None, "paired_pace")
    assert ei.value.code == 2
    InvariantGuard.require_sealed_keep(None, "single_shot")
