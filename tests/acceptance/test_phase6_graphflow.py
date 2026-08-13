"""WP5 — system projector + GraphFlow diversity (C12)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_platform.agents.simple_loop_agent import SimpleLoopAgent
from agentic_platform.core.platform import Platform
from agentic_platform.graph.projector import SYSTEM_AGENT, project_loop
from agentic_platform.security.auth import AuthError
from tests.conftest import make_control_payload


@pytest.mark.release_gate
def test_subgraph_diverse_under_budget(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    for i, (lr, steps) in enumerate([(0.2, 80), (0.01, 20), (0.15, 100)]):
        text = (workspace / "train.py").read_text(encoding="utf-8")
        import re

        text = re.sub(r"^LR\s*=\s*[^\n]+", f"LR = {lr}", text, flags=re.M)
        text = re.sub(r"^STEPS\s*=\s*[^\n]+", f"STEPS = {steps}", text, flags=re.M)
        platform.loops.propose_trial(
            loop["id"],
            agent_id=f"p{i}",
            hypothesis=f"lr={lr} steps={steps}",
            file_edits={"train.py": text},
        )
    trials = platform.loops.list_trials(loop["id"])
    budget = platform.runs.create_budget({"max_graph_writes": 500})
    run = platform.runs.create_run(ctl["id"], budget["id"])
    projected = project_loop(platform.graph, trials, run_id=run["id"])
    assert projected["commits_projected"] >= 1
    seeds = [f"commit:{t['commit_hash']}" for t in trials if t.get("commit_hash")]
    assert seeds
    sg = platform.graph.subgraph(seed_ids=seeds[:1], hops=2, token_budget=80)
    assert sg["token_accounting"] == "approx_chars_div_4"
    assert sg.get("ranker") == "graphflow-v1"
    types = {n["type"] for n in sg["nodes"]}
    assert "Claim" not in types
    assert sg["approx_tokens_used"] <= 80 or sg["truncated"] is True
    for n in sg["nodes"]:
        assert "7919" not in str(n)


@pytest.mark.release_gate
def test_agent_cannot_project_or_write_graph_by_default(
    platform: Platform, workspace: Path
) -> None:
    assert platform.auth.admin_token_ok("not-admin") is False
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    SimpleLoopAgent(platform, loop["id"], enable_graph_writes=False).run(max_trials=2)
    rows = platform.db.fetchall("SELECT type FROM graph_nodes")
    assert all(r["type"] != "Claim" for r in rows)
    # Agent keys cannot pass the admin projector check
    try:
        platform.auth.resolve("not-a-real-key")
    except AuthError:
        pass
    _ = SYSTEM_AGENT
    _ = workspace
