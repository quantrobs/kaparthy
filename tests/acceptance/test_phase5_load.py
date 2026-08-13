"""Phase 5 — concurrent loop trials / recovery under load."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agentic_platform.core.platform import Platform
from tests.conftest import make_control_payload


def _set_lr(workspace: Path, lr: float) -> str:
    text = (workspace / "train.py").read_text(encoding="utf-8")
    return re.sub(r"^LR\s*=\s*[^\n]+", f"LR = {lr}", text, flags=re.M)


def test_sequential_burst_trials_remain_consistent(platform: Platform, workspace: Path) -> None:
    """Burst of trials: every kept improves best; crash recovery works mid-burst."""
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    best = loop["best_metric"]
    assert best is not None

    lrs = [0.01, 0.03, 0.05, 0.08, 0.1, 0.12, 0.15, 0.2, 0.04, 0.09]
    for i, lr in enumerate(lrs):
        if i == 4:
            # inject crash mid-burst
            t = platform.loops.propose_trial(
                loop["id"],
                agent_id="load",
                hypothesis=f"crash at {i}",
                file_edits={"train.py": _set_lr(workspace, lr)},
                simulate_crash=True,
            )
            assert t["status"] == "crash"
            rec = platform.loops.recover(loop["id"])
            assert rec["recovered"]
            continue
        t = platform.loops.propose_trial(
            loop["id"],
            agent_id="load",
            hypothesis=f"lr={lr}",
            file_edits={"train.py": _set_lr(workspace, lr)},
        )
        assert t["status"] in ("kept", "reverted", "rejected", "crash")
        if t["status"] == "kept":
            cur = platform.loops.get(loop["id"])
            assert cur["best_metric"] <= best + 1e-9
            best = cur["best_metric"]

    info = platform.loops.best(loop["id"])
    assert info["reproducible_from_commit"] is True


def test_parallel_board_posts_survive(platform: Platform) -> None:
    def post(i: int) -> str:
        return platform.dag.board_post(f"agent-{i % 4}", f"note {i}", commit_hash=None)["id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(post, i) for i in range(40)]
        ids = [f.result() for f in as_completed(futs)]
    assert len(ids) == 40
    assert len(platform.dag.board_list()) >= 40
