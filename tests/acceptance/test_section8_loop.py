"""§8 Acceptance — Loop (hostile metrics, no override keep)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from agentic_platform.core.platform import Platform
from tests.conftest import make_control_payload


def _set_hparams(workspace: Path, lr: float, steps: int, hidden: int = 8) -> str:
    text = (workspace / "train.py").read_text(encoding="utf-8")
    text = re.sub(r"^LR\s*=\s*[^\n]+", f"LR = {lr}", text, flags=re.M)
    text = re.sub(r"^STEPS\s*=\s*[^\n]+", f"STEPS = {steps}", text, flags=re.M)
    text = re.sub(r"^HIDDEN\s*=\s*[^\n]+", f"HIDDEN = {hidden}", text, flags=re.M)
    return text


def test_reproducible_best_after_real_trials(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    assert (workspace / "program.md").exists()
    assert loop["best_metric"] is not None

    # Grid of real train.py runs (no metric_override)
    configs = [
        (0.01, 20, 4),
        (0.05, 40, 8),
        (0.1, 60, 8),
        (0.15, 80, 12),
        (0.08, 120, 8),
        (0.2, 40, 16),
        (0.03, 80, 12),
        (0.12, 100, 8),
    ]
    kept = 0
    for i, (lr, steps, hidden) in enumerate(configs):
        content = _set_hparams(workspace, lr, steps, hidden)
        t = platform.loops.propose_trial(
            loop["id"],
            agent_id=f"agent-{i % 3}",
            hypothesis=f"lr={lr} steps={steps} h={hidden}",
            file_edits={"train.py": content},
        )
        assert t["status"] in ("kept", "reverted", "crash", "rejected")
        assert "metric_override" not in (t.get("error") or "") or t["status"] == "rejected"
        if t["status"] == "kept":
            kept += 1
            assert t["metric_value"] is not None

    info = platform.loops.best(loop["id"])
    assert info["best_commit"]
    # Reproducibility is computed, not hardcoded True
    assert isinstance(info["reproducible_from_commit"], bool)
    if info["best_metric"] is not None:
        repro = platform.loops.reproduce_metric(loop["id"], info["best_commit"])
        assert repro["matches_recorded_best"] is True
        assert info["reproducible_from_commit"] is True


@pytest.mark.release_gate
def test_metric_override_cannot_keep(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    t = platform.loops.propose_trial(
        loop["id"],
        agent_id="cheater",
        hypothesis="fake metric",
        metric_override=0.0001,
    )
    assert t["status"] == "rejected"
    assert "INV-02" in (t.get("error") or "")
    refreshed = platform.loops.get(loop["id"])
    assert refreshed["best_commit"] == loop["best_commit"]


@pytest.mark.release_gate
def test_crash_mid_training_reverts_and_logs(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    parent = loop["best_commit"]

    trial = platform.loops.propose_trial(
        loop["id"],
        agent_id="crashy",
        hypothesis="will crash",
        file_edits={"train.py": _set_hparams(workspace, 0.1, 40)},
        simulate_crash=True,
    )
    assert trial["status"] == "crash"
    assert trial["error"]
    assert trial["ledger_entry_uri"]

    refreshed = platform.loops.get(loop["id"])
    assert refreshed["best_commit"] == parent

    next_t = platform.loops.propose_trial(
        loop["id"],
        agent_id="recover",
        hypothesis="after crash",
        file_edits={"train.py": _set_hparams(workspace, 0.2, 80, 12)},
    )
    assert next_t["parent_commit"] == parent
    assert next_t["status"] in ("kept", "reverted")


@pytest.mark.release_gate
def test_protected_path_rejected_before_commit(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)

    trial = platform.loops.propose_trial(
        loop["id"],
        agent_id="rogue",
        hypothesis="edit prepare",
        file_edits={"prepare.py": "# HACKED\n"},
    )
    assert trial["status"] == "rejected"
    assert "INV-01" in (trial.get("error") or "")
    assert trial.get("commit_hash") is None


@pytest.mark.release_gate
def test_mutable_allowlist_rejects_extra_files(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    trial = platform.loops.propose_trial(
        loop["id"],
        agent_id="rogue2",
        hypothesis="touch secrets",
        file_edits={"secrets.txt": "x"},
    )
    assert trial["status"] == "rejected"
    assert "mutable" in (trial.get("error") or "").lower() or "INV-01" in (trial.get("error") or "")
