"""Shared demo control-document factory (DEMO-CTL-001)."""

from __future__ import annotations

from typing import Any


def demo_control_payload() -> dict[str, Any]:
    """Canonical control document for the CPU-trainer demo loop."""
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
        "created_by": "demo",
    }
