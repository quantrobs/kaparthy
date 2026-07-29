from __future__ import annotations

import os
from pathlib import Path

import pytest

from agentic_platform.core.platform import Platform


@pytest.fixture()
def platform(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Platform:
    data = tmp_path / "data"
    monkeypatch.setenv("AGENTIC_DATA", str(data))
    # Ensure contracts resolve from repo root
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("AGENTIC_ROOT", str(root))
    p = Platform(data)
    yield p
    p.close()


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "prepare.py").write_text("# protected evaluation surface\nprint('ready')\n", encoding="utf-8")
    (ws / "train.py").write_text("metric = 1.0\nprint(f'val_loss={metric}')\n", encoding="utf-8")
    (ws / "program.md").write_text("Minimize val_loss. Only edit train.py.\n", encoding="utf-8")
    return ws


def make_control_payload() -> dict:
    return {
        "objective": "Minimize validation loss via small train.py edits",
        "protected_paths": ["prepare.py"],
        "metric": {
            "name": "val_loss",
            "direction": "minimize",
            "parse_regex": r"val_loss=([0-9.]+)",
            "unit": "loss",
        },
        "comparison": {"function": "strictly_better"},
        "run_command": "python train.py",
        "time_budget_seconds": 30,
        "keep_criteria": "strictly lower val_loss",
        "escalation_criteria": "human if 10 consecutive reverts",
        "exhaustion_criteria": "stop after budget or plateaus",
        "mutable_paths": ["train.py"],
        "program_md": "Edit train.py only. Never touch prepare.py.",
        "created_by": "architect",
    }
