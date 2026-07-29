"""§8 Acceptance — End-to-End."""

from __future__ import annotations

import re
from pathlib import Path

from agentic_platform.core.platform import Platform
from tests.conftest import make_control_payload


def _hparams(workspace: Path, lr: float, steps: int) -> str:
    text = (workspace / "train.py").read_text(encoding="utf-8")
    text = re.sub(r"^LR\s*=\s*[^\n]+", f"LR = {lr}", text, flags=re.M)
    text = re.sub(r"^STEPS\s*=\s*[^\n]+", f"STEPS = {steps}", text, flags=re.M)
    return text


def test_full_audit_trail_reconstructs_traceability(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    budget = platform.runs.create_budget(
        {
            "max_model_calls": 100,
            "max_tokens": 100000,
            "max_graph_writes": 100,
            "max_wall_clock_seconds": 3600,
            "max_cost_usd": 10.0,
        }
    )
    run = platform.runs.create_run(ctl["id"], budget["id"])

    loop = platform.loops.start(ctl["id"], workspace, agent_id="e2e-agent")
    # Try a few real configs until we get a keep or accept best as baseline-only
    trial = None
    for lr, steps in [(0.2, 80), (0.15, 100), (0.1, 60), (0.05, 40)]:
        trial = platform.loops.propose_trial(
            loop["id"],
            agent_id="e2e-agent",
            hypothesis=f"lr={lr}",
            file_edits={"train.py": _hparams(workspace, lr, steps)},
        )
        if trial["status"] == "kept":
            break
    assert trial is not None

    # Push real commit to hub for Git-authoritative annotation
    if trial.get("commit_hash") and trial["status"] == "kept":
        platform.dag.push(
            workspace,
            agent_id="e2e-agent",
            hypothesis=trial["hypothesis"],
            metric_name=trial.get("metric_name"),
            metric_value=trial.get("metric_value"),
            status="kept",
        )
        platform.runs.audit(run["id"], "dag.push", {"hash": trial["commit_hash"]})
    else:
        # Still push current best for lineage
        best = platform.loops.get(loop["id"])
        platform.dag.push(
            workspace,
            agent_id="e2e-agent",
            hypothesis="baseline-or-reverted",
            metric_value=best.get("best_metric"),
            status="evidence",
        )
        platform.runs.audit(run["id"], "dag.push", {"hash": best.get("best_commit")})

    platform.graph.apply_update(
        {
            "run_id": run["id"],
            "agent_id": "e2e-agent",
            "nodes": [
                {
                    "id": "src1",
                    "type": "Source",
                    "label": "trial ledger",
                    "properties": {"uri": trial.get("ledger_entry_uri") or "n/a"},
                },
                {
                    "id": "cl1",
                    "type": "Claim",
                    "label": "metric path exercised",
                    "provenance": {
                        "source_ids": ["src1"],
                        "run_id": run["id"],
                        "is_inference": False,
                    },
                },
                {
                    "id": "cmt1",
                    "type": "Commit",
                    "label": (trial.get("commit_hash") or "none")[:12],
                    "properties": {"hash": trial.get("commit_hash")},
                },
            ],
            "edges": [
                {"id": "es1", "type": "SUPPORTS", "source": "src1", "target": "cl1"},
                {"id": "es2", "type": "PRODUCED", "source": "cmt1", "target": "cl1"},
            ],
        }
    )

    ev = platform.eval.create(
        {
            "decision": "pass" if trial["status"] == "kept" else "revise",
            "target": trial.get("commit_hash") or loop["best_commit"],
            "rubric": "strictly_better val_loss vs baseline from real run_command",
            "confidence": 0.99,
            "evidence_edge_ids": ["es1", "es2"],
            "run_id": run["id"],
        }
    )

    platform.runs.consume(run["id"], model_calls=1, tokens=500)
    completed = platform.runs.complete(
        run["id"],
        partial_result={
            "objective": ctl["objective"],
            "plan": ctl.get("program_md"),
            "best_commit": platform.loops.get(loop["id"]).get("best_commit"),
            "evaluation_id": ev["id"],
        },
    )
    assert completed["status"] == "completed"

    audit = platform.runs.get_audit_trail(run["id"])
    assert audit["run"]["id"] == run["id"]
    kinds = {e["kind"] for e in audit["events"]}
    assert "run.created" in kinds
    assert "eval.created" in kinds
    t = audit["traceability"]
    assert t["objective"] and t["plan"] and t["runs"] and t["budgets"]
    assert t["evaluations"]
    assert t["claims"]
    assert t["commits"]


def test_budget_exhaustion_returns_structured_partial(platform: Platform) -> None:
    ctl = platform.control.create(make_control_payload())
    budget = platform.runs.create_budget(
        {
            "max_model_calls": 2,
            "max_tokens": 1000,
            "max_graph_writes": 5,
        }
    )
    run = platform.runs.create_run(ctl["id"], budget["id"])
    platform.runs.consume(run["id"], model_calls=1)
    exhausted = platform.runs.consume(run["id"], model_calls=2)
    assert exhausted["status"] == "budget_exhausted"
    assert exhausted["partial_result"] is not None
    assert exhausted["partial_result"]["reason"].startswith("budget_exhausted")
    assert exhausted["stop_reason"]
    try:
        platform.runs.consume(run["id"], model_calls=1)
        assert False, "should have rejected consumption after exhaustion"
    except Exception as e:
        assert "INV-11" in str(e) or "not accepting" in str(e).lower() or "budget" in str(e).lower()
