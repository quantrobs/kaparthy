"""DEMO-TEST-001 — bootstrap, hostile reject, athlete smoke."""

from __future__ import annotations

from pathlib import Path

from agentic_platform.agents.simple_loop_agent import SimpleLoopAgent
from agentic_platform.core.platform import Platform
from agentic_platform.demo.bootstrap import bootstrap_demo
from agentic_platform.demo.hostile import run_hostile_reject


def test_bootstrap_yields_baseline_metric(tmp_path: Path) -> None:
    data = tmp_path / "data"
    ws = tmp_path / "ws"
    result = bootstrap_demo(data, workspace=ws, agent_id="demo")
    assert result["best_metric"] is not None
    assert result["loop_id"]
    assert result["control_id"]
    assert (Path(result["workspace_path"]) / "train.py").exists()
    assert (Path(result["workspace_path"]) / "prepare.py").exists()
    assert (Path(result["workspace_path"]) / "program.md").exists()


def test_hostile_override_rejected(tmp_path: Path) -> None:
    data = tmp_path / "data"
    result = bootstrap_demo(data, workspace=tmp_path / "ws")
    p = Platform(data)
    try:
        out = run_hostile_reject(p, result["loop_id"])
        assert out["passed"] is True
        assert out["best_unchanged"] is True
        assert out["override_trial"]["status"] == "rejected"
        assert "INV-02" in (out["override_trial"].get("error") or "")
        assert out["protected_trial"] is None
    finally:
        p.close()


def test_hostile_also_protected(tmp_path: Path) -> None:
    data = tmp_path / "data"
    result = bootstrap_demo(data, workspace=tmp_path / "ws")
    p = Platform(data)
    try:
        out = run_hostile_reject(p, result["loop_id"], also_protected=True)
        assert out["passed"] is True
        assert out["protected_trial"] is not None
        assert out["protected_trial"]["status"] == "rejected"
        assert "INV-01" in (out["protected_trial"].get("error") or "")
    finally:
        p.close()


def test_athlete_smoke_three_trials(tmp_path: Path) -> None:
    data = tmp_path / "data"
    boot = bootstrap_demo(data, workspace=tmp_path / "ws")
    start = boot["best_metric"]
    p = Platform(data)
    try:
        agent = SimpleLoopAgent(
            p, boot["loop_id"], agent_id="simple-agent", enable_graph_writes=False
        )
        summary = agent.run(max_trials=3)
        assert summary["trials"] == 3
        end = p.loops.get(boot["loop_id"])
        assert end is not None
        assert end["best_metric"] is not None
        assert end["best_metric"] <= start + 1e-9
    finally:
        p.close()
