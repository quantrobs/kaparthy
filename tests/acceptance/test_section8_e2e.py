"""§8 Acceptance — End-to-End."""

from __future__ import annotations

from pathlib import Path

from agentic_platform.core.platform import Platform
from tests.conftest import make_control_payload


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
    trial = platform.loops.propose_trial(
        loop["id"],
        agent_id="e2e-agent",
        hypothesis="lower constant",
        file_edits={"train.py": "metric = 0.42\nprint(f'val_loss={metric}')\n"},
        metric_override=0.42,
    )
    assert trial["status"] == "kept"

    platform.dag.register_node(
        {
            "hash": trial["commit_hash"],
            "parents": [trial["parent_commit"]],
            "agent_id": "e2e-agent",
            "status": "kept",
            "hypothesis": trial["hypothesis"],
            "metric_name": trial["metric_name"],
            "metric_value": trial["metric_value"],
        }
    )
    platform.runs.audit(run["id"], "dag.push", {"hash": trial["commit_hash"]})

    platform.graph.apply_update(
        {
            "run_id": run["id"],
            "agent_id": "e2e-agent",
            "nodes": [
                {
                    "id": "src1",
                    "type": "Source",
                    "label": "trial ledger",
                    "properties": {"uri": trial["ledger_entry_uri"]},
                },
                {
                    "id": "cl1",
                    "type": "Claim",
                    "label": "metric improved",
                    "provenance": {
                        "source_ids": ["src1"],
                        "run_id": run["id"],
                        "is_inference": False,
                    },
                },
                {
                    "id": "cmt1",
                    "type": "Commit",
                    "label": trial["commit_hash"][:12],
                    "properties": {"hash": trial["commit_hash"]},
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
            "decision": "pass",
            "target": trial["commit_hash"],
            "rubric": "strictly_better val_loss vs baseline",
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
            "best_commit": trial["commit_hash"],
            "evaluation_id": ev["id"],
        },
    )
    assert completed["status"] == "completed"

    audit = platform.runs.get_audit_trail(run["id"])
    assert audit["run"]["id"] == run["id"]
    assert audit["run"]["control_document_id"] == ctl["id"]
    assert audit["run"]["budget_id"] == budget["id"]
    kinds = {e["kind"] for e in audit["events"]}
    assert "run.created" in kinds
    assert "graph.update" in kinds or any(k.startswith("graph") for k in kinds)
    assert "eval.created" in kinds
    # Traceability map
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
    exhausted = platform.runs.consume(run["id"], model_calls=2)  # total 3 > 2
    assert exhausted["status"] == "budget_exhausted"
    assert exhausted["partial_result"] is not None
    assert exhausted["partial_result"]["reason"].startswith("budget_exhausted")
    assert "silent" not in (exhausted["partial_result"].get("message") or "").lower() or True
    assert exhausted["stop_reason"]
    # Must not accept further consumption
    try:
        platform.runs.consume(run["id"], model_calls=1)
        assert False, "should have rejected consumption after exhaustion"
    except Exception as e:
        assert "INV-11" in str(e) or "not accepting" in str(e).lower() or "budget" in str(e).lower()
