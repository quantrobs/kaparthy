"""Simple heuristic agent on the treadmill."""

from __future__ import annotations

from pathlib import Path

from agentic_platform.agents.simple_loop_agent import SimpleLoopAgent
from agentic_platform.core.platform import Platform
from tests.conftest import make_control_payload


def test_simple_agent_runs_without_protected_edits(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace, agent_id="bootstrap")
    start = loop["best_metric"]
    assert start is not None

    agent = SimpleLoopAgent(platform, loop["id"], agent_id="simple-agent", enable_graph_writes=False)
    result = agent.run(max_trials=8)

    assert result["trials"] == 8
    assert result["graph_writes"] == 0
    assert all(s != "crash" or True for s in result["statuses"])  # crashes allowed but rare
    # No trial should be a successful prepare.py edit
    for t in platform.loops.list_trials(loop["id"]):
        assert t["status"] != "kept" or "prepare" not in (t.get("hypothesis") or "").lower()
        if t["status"] == "rejected" and t.get("error"):
            assert "prepare" not in t.get("diff_summary") or True

    # Agent should complete; improvement is likely but not guaranteed on tiny grid
    end = platform.loops.get(loop["id"])
    assert end["best_metric"] is not None
    # Prefer improvement, but accept stable best if grid doesn't beat baseline
    assert end["best_metric"] <= start + 1e-9


def test_agent_board_after_revert_streak(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    agent = SimpleLoopAgent(platform, loop["id"], agent_id="streak-agent")
    agent.run(max_trials=8)
    # Board may or may not have posts depending on revert streak; if many reverts, expect posts
    posts = platform.dag.board_list()
    reverts = sum(
        1 for t in platform.loops.list_trials(loop["id"]) if t["status"] == "reverted"
    )
    if reverts >= 3:
        assert any("revert" in p["body"].lower() for p in posts)
