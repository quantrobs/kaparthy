"""WP3 — leaf parent + evidence push (C1/C3)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from agentic_platform.core.platform import Platform
from tests.conftest import make_control_payload


def _set(workspace: Path, lr: float, steps: int, hidden: int = 8) -> str:
    text = (workspace / "train.py").read_text(encoding="utf-8")
    text = re.sub(r"^LR\s*=\s*[^\n]+", f"LR = {lr}", text, flags=re.M)
    text = re.sub(r"^STEPS\s*=\s*[^\n]+", f"STEPS = {steps}", text, flags=re.M)
    text = re.sub(r"^HIDDEN\s*=\s*[^\n]+", f"HIDDEN = {hidden}", text, flags=re.M)
    return text


@pytest.mark.release_gate
def test_reverted_commit_is_hub_leaf(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    parent = loop["best_commit"]
    # A likely-worse config so we get a revert, but it must still land on the hub.
    t = platform.loops.propose_trial(
        loop["id"],
        agent_id="explorer",
        hypothesis="lr=0.01 steps=20 likely revert-or-keep",
        file_edits={"train.py": _set(workspace, 0.01, 20, 4)},
        parent_commit=parent,
    )
    if t["status"] == "kept":
        # force a second child that is worse
        t2 = platform.loops.propose_trial(
            loop["id"],
            agent_id="explorer",
            hypothesis="lr=9.9 steps=20",
            file_edits={"train.py": _set(workspace, 9.9, 20, 4)},
            parent_commit=parent,
        )
        assert t2["status"] in ("reverted", "rejected", "crash")
        if t2.get("commit_hash"):
            node = platform.dag.fetch(t2["commit_hash"])
            assert node is not None
            assert node["status"] in ("reverted", "evidence")
            leaves = {n["hash"] for n in platform.dag.leaves()}
            assert t2["commit_hash"] in leaves
        return
    assert t["status"] in ("reverted", "crash", "rejected")
    if t.get("commit_hash"):
        node = platform.dag.fetch(t["commit_hash"])
        assert node is not None
        leaves = {n["hash"] for n in platform.dag.leaves()}
        assert t["commit_hash"] in leaves


@pytest.mark.release_gate
def test_nonbest_parent_keep_vs_global(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    root = loop["best_commit"]
    t1 = platform.loops.propose_trial(
        loop["id"],
        agent_id="a",
        hypothesis="lr=0.2 steps=80",
        file_edits={"train.py": _set(workspace, 0.2, 80)},
        parent_commit=root,
    )
    # Branch a second child from the original root (not from t1).
    t2 = platform.loops.propose_trial(
        loop["id"],
        agent_id="b",
        hypothesis="lr=0.15 steps=100 from root",
        file_edits={"train.py": _set(workspace, 0.15, 100)},
        parent_commit=root,
    )
    assert t2["parent_commit"] == root
    if t2["status"] == "kept":
        best = platform.loops.get(loop["id"])["best_metric"]
        assert t2["metric_value"] is not None
        assert best == t2["metric_value"]
    elif t2["status"] == "reverted":
        # Must not have beaten the global best
        best = platform.loops.get(loop["id"])["best_metric"]
        if t2.get("metric_value") is not None and best is not None:
            assert t2["metric_value"] >= best - 1e-12
    # Two children of root exist as hub nodes when they committed
    kids = platform.dag.children(root)
    hashes = {k["hash"] for k in kids}
    for t in (t1, t2):
        if t.get("commit_hash"):
            assert t["commit_hash"] in hashes
