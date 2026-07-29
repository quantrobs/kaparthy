"""§8 Acceptance — Loop."""

from __future__ import annotations

from pathlib import Path

from agentic_platform.core.platform import Platform
from tests.conftest import make_control_payload


def test_reproducible_best_after_many_trials(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)

    # Autonomous-style batch: 50 trials with deterministic metric_override for speed
    best = 1.0
    for i in range(50):
        # every 5th trial improves
        candidate = best - 0.01 if i % 5 == 0 else best + 0.05
        t = platform.loops.propose_trial(
            loop["id"],
            agent_id=f"agent-{i % 3}",
            hypothesis=f"trial {i}",
            file_edits={"train.py": f"metric = {candidate}\nprint(f'val_loss={{metric}}')\n"},
            metric_override=candidate,
        )
        if t["status"] == "kept":
            best = candidate

    info = platform.loops.best(loop["id"])
    assert info["best_commit"]
    assert info["reproducible_from_commit"] is True

    # Re-run from commit hash alone (uses real train.py content)
    # Rewrite train.py to match last kept metric for real execution path
    platform.loops.propose_trial(
        loop["id"],
        agent_id="repro",
        hypothesis="sync for repro",
        file_edits={"train.py": f"metric = {info['best_metric']}\nprint(f'val_loss={{metric}}')\n"},
        metric_override=info["best_metric"],
    )
    info = platform.loops.best(loop["id"])
    repro = platform.loops.reproduce_metric(loop["id"], info["best_commit"])
    assert repro["matches_recorded_best"] is True


def test_crash_mid_training_reverts_and_logs(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    parent = loop["best_commit"]

    trial = platform.loops.propose_trial(
        loop["id"],
        agent_id="crashy",
        hypothesis="will crash",
        file_edits={"train.py": "metric = 0.1\nprint(f'val_loss={metric}')\n"},
        simulate_crash=True,
    )
    assert trial["status"] == "crash"
    assert trial["error"]
    assert trial["ledger_entry_uri"]

    refreshed = platform.loops.get(loop["id"])
    assert refreshed["best_commit"] == parent

    # Next trial resumes from last kept state
    next_t = platform.loops.propose_trial(
        loop["id"],
        agent_id="recover",
        hypothesis="after crash",
        file_edits={"train.py": "metric = 0.5\nprint(f'val_loss={metric}')\n"},
        metric_override=0.5,
    )
    assert next_t["parent_commit"] == parent
    assert next_t["status"] == "kept"


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
