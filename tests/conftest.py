from __future__ import annotations

from pathlib import Path

import pytest

from agentic_platform.core.platform import Platform


@pytest.fixture()
def platform(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Platform:
    data = tmp_path / "data"
    monkeypatch.setenv("AGENTIC_DATA", str(data))
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("AGENTIC_ROOT", str(root))
    # Never allow orphan DAG metadata in tests unless a test opts in
    monkeypatch.delenv("AGENTIC_DAG_ALLOW_ORPHAN_META", raising=False)
    monkeypatch.setenv("AGENTIC_REQUIRE_AUTH", "0")
    # Allow tests to construct Platform before flipping auth flags per-test
    monkeypatch.delenv("AGENTIC_ALLOW_ARBITRARY_RUN_CMD", raising=False)
    p = Platform(data)
    yield p
    p.close()


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Empty workspace — LoopService seeds the real demo trainer."""
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


def make_control_payload() -> dict:
    return {
        "objective": "Minimize validation loss via small train.py hyperparameter edits",
        "protected_paths": ["prepare.py"],
        "mutable_paths": ["train.py", "program.md"],
        "metric": {
            "name": "val_loss",
            "direction": "minimize",
            "parse_regex": r"val_loss=([0-9.eE+-]+)",
            "unit": "loss",
        },
        "comparison": {"function": "strictly_better"},
        "run_command": "python train.py",
        "time_budget_seconds": 30,
        "keep_criteria": "strictly lower val_loss from real run_command output",
        "escalation_criteria": "human if 10 consecutive reverts",
        "exhaustion_criteria": "stop after budget or plateaus",
        "program_md": "Edit train.py hyperparameters only. Never touch prepare.py.",
        "created_by": "architect",
    }
