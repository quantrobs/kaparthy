"""Hostile-metric demo punchline (DEMO-HOST-001)."""

from __future__ import annotations

from typing import Any

from agentic_platform.core.platform import Platform


def run_hostile_reject(
    platform: Platform,
    loop_id: str,
    agent_id: str = "demo-hostile",
    also_protected: bool = False,
) -> dict[str, Any]:
    """Prove metric_override cannot keep (INV-02); optional protected-path reject."""
    loop = platform.loops.get(loop_id)
    if not loop:
        raise ValueError(f"unknown loop: {loop_id}")

    snap_metric = loop.get("best_metric")
    snap_commit = loop.get("best_commit")

    override_trial = platform.loops.propose_trial(
        loop_id,
        agent_id=agent_id,
        hypothesis="demo: metric_override cheat",
        metric_override=0.0001,
    )

    errors: list[str] = []
    if override_trial.get("status") != "rejected":
        errors.append(f"override status={override_trial.get('status')!r}, expected rejected")
    err = override_trial.get("error") or ""
    if "INV-02" not in err:
        errors.append(f"override error missing INV-02: {err!r}")

    protected_trial: dict[str, Any] | None = None
    if also_protected:
        protected_trial = platform.loops.propose_trial(
            loop_id,
            agent_id=agent_id,
            hypothesis="demo: edit protected prepare.py",
            file_edits={"prepare.py": "# HACKED by demo\n"},
        )
        if protected_trial.get("status") != "rejected":
            errors.append(
                f"protected status={protected_trial.get('status')!r}, expected rejected"
            )
        perr = protected_trial.get("error") or ""
        if "INV-01" not in perr:
            errors.append(f"protected error missing INV-01: {perr!r}")

    refreshed = platform.loops.get(loop_id) or {}
    best_unchanged = (
        refreshed.get("best_metric") == snap_metric
        and refreshed.get("best_commit") == snap_commit
    )
    if not best_unchanged:
        errors.append(
            f"best changed: metric {snap_metric!r}->{refreshed.get('best_metric')!r}, "
            f"commit {snap_commit!r}->{refreshed.get('best_commit')!r}"
        )

    return {
        "override_trial": override_trial,
        "protected_trial": protected_trial,
        "best_unchanged": best_unchanged,
        "passed": len(errors) == 0,
        "errors": errors,
        "best_metric": refreshed.get("best_metric"),
        "best_commit": refreshed.get("best_commit"),
    }
