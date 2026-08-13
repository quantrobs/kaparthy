"""System lineage projector (WP5). Never writes Claims."""

from __future__ import annotations

from typing import Any

from agentic_platform.core.ids import new_id
from agentic_platform.graph.service import GraphService


SYSTEM_AGENT = "system-projector"


def project_trial(graph: GraphService, trial: dict[str, Any], run_id: str = "system-projector") -> int:
    commit = trial.get("commit_hash")
    if not commit:
        return 0
    parent = trial.get("parent_commit")
    nodes: list[dict[str, Any]] = [
        {
            "id": f"commit:{commit}",
            "type": "Commit",
            "label": (trial.get("hypothesis") or commit)[:80],
            "properties": {
                "hash": commit,
                "status": trial.get("status"),
                "agent_id": trial.get("agent_id"),
                "hypothesis": (trial.get("hypothesis") or "")[:200],
            },
        }
    ]
    edges: list[dict[str, Any]] = []
    if parent:
        nodes.append(
            {
                "id": f"commit:{parent}",
                "type": "Commit",
                "label": parent[:12],
                "properties": {"hash": parent},
            }
        )
        edges.append(
            {
                "id": f"e_parent_{commit[:12]}",
                "type": "PARENT_OF",
                "source": f"commit:{parent}",
                "target": f"commit:{commit}",
            }
        )
    if trial.get("metric_value") is not None:
        mid = f"metric:{commit}:{trial.get('metric_name') or 'metric'}"
        nodes.append(
            {
                "id": mid,
                "type": "Metric",
                "label": str(trial.get("metric_name") or "metric"),
                "properties": {
                    "name": trial.get("metric_name"),
                    "value": trial.get("metric_value"),
                },
            }
        )
        edges.append(
            {
                "id": f"e_metric_{commit[:12]}",
                "type": "HAS_METRIC",
                "source": f"commit:{commit}",
                "target": mid,
            }
        )
    cert = trial.get("keep_certificate")
    eid = f"eval:{trial['id']}"
    nodes.append(
        {
            "id": eid,
            "type": "Evaluation",
            "label": trial.get("status") or "eval",
            "properties": {
                "decision": trial.get("status"),
                "sealed": bool(cert),
                "e_value": None if not cert else cert.get("e_value"),
                "wins": None if not cert else cert.get("wins"),
            },
        }
    )
    edges.append(
        {
            "id": f"e_eval_{trial['id']}",
            "type": "EVALUATED_BY",
            "source": f"commit:{commit}",
            "target": eid,
        }
    )
    result = graph.apply_update(
        {
            "run_id": run_id,
            "agent_id": SYSTEM_AGENT,
            "nodes": nodes,
            "edges": edges,
        }
    )
    return int(result.get("writes") or 0)


def project_loop(graph: GraphService, trials: list[dict[str, Any]], run_id: str | None = None) -> dict[str, Any]:
    writes = 0
    commits = 0
    rid = run_id or f"proj_{new_id('run_')}"
    for trial in trials:
        n = project_trial(graph, trial, run_id=rid)
        writes += n
        if trial.get("commit_hash"):
            commits += 1
    return {"writes": writes, "commits_projected": commits, "run_id": rid}
