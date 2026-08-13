"""Heuristic leaf-search agent (WP3 / C1+C3). No LLM."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agentic_platform.core.platform import Platform
from agentic_platform.loops.fingerprint import HPARAM_NAMES, parse_hparams

_STEPS = {
    "LR": [0.01, 0.03, 0.05, 0.08, 0.1, 0.15, 0.2],
    "STEPS": [20, 40, 60, 80, 120],
    "HIDDEN": [4, 8, 12, 16],
    "L2": [0.0, 1e-4, 1e-3],
}


class LeafSearchAgent:
    def __init__(
        self,
        platform: Platform,
        loop_id: str,
        agent_id: str = "leaf-agent",
        enable_graph_writes: bool = False,
    ) -> None:
        self.platform = platform
        self.loop_id = loop_id
        self.agent_id = agent_id
        self.enable_graph_writes = enable_graph_writes
        self._lineage_reverts: dict[str, int] = {}

    def run(self, max_trials: int = 8) -> dict[str, Any]:
        loop = self.platform.loops.get(self.loop_id)
        if not loop:
            raise ValueError(f"unknown loop: {self.loop_id}")
        history: list[dict[str, Any]] = []
        start_best = loop.get("best_metric")

        for i in range(max_trials):
            loop = self.platform.loops.get(self.loop_id) or loop
            workspace = Path(loop["workspace_path"])
            parent, axis, value, note = self._choose(workspace, loop, i)
            text = (workspace / "train.py").read_text(encoding="utf-8") if (workspace / "train.py").exists() else ""
            if parent:
                try:
                    from agentic_platform.storage.git_repo import GitWorkspace

                    GitWorkspace(workspace).reset_hard(parent)
                    text = (workspace / "train.py").read_text(encoding="utf-8")
                except Exception:
                    parent = loop.get("best_commit")
                    text = (workspace / "train.py").read_text(encoding="utf-8") if (workspace / "train.py").exists() else ""
            new = re.sub(
                rf"^({axis}\s*=\s*)[^\n]+",
                rf"\g<1>{value}",
                text,
                count=1,
                flags=re.MULTILINE,
            )
            if new == text:
                continue
            trial = self.platform.loops.propose_trial(
                self.loop_id,
                agent_id=self.agent_id,
                hypothesis=note,
                file_edits={"train.py": new},
                parent_commit=parent,
            )
            history.append(trial)
            key = parent or "root"
            if trial["status"] == "reverted":
                self._lineage_reverts[key] = self._lineage_reverts.get(key, 0) + 1
                if self._lineage_reverts[key] >= 3:
                    self.platform.dag.board_post(
                        self.agent_id,
                        f"leaf exhausted parent={(parent or '')[:12]} last={trial.get('metric_value')}",
                        commit_hash=parent,
                    )
                    self._lineage_reverts[key] = 0
            elif trial["status"] == "kept":
                self._lineage_reverts[key] = 0
                metrics = [
                    t.get("metric_value")
                    for t in history
                    if t.get("metric_value") is not None
                ]
                if len(metrics) >= 3 and trial.get("metric_value") is not None:
                    mean = sum(float(m) for m in metrics) / len(metrics)
                    if abs(float(trial["metric_value"]) - mean) > 2 * (abs(mean) * 0.1 + 1e-6):
                        self.platform.dag.board_post(
                            self.agent_id,
                            f"leaf surprising metric={trial['metric_value']} vs mean={mean:.4f}",
                            commit_hash=trial.get("commit_hash"),
                        )

        end = self.platform.loops.get(self.loop_id) or loop
        return {
            "loop_id": self.loop_id,
            "trials": len(history),
            "statuses": [t["status"] for t in history],
            "start_best": start_best,
            "end_best": end.get("best_metric"),
            "kept": sum(1 for t in history if t["status"] == "kept"),
            "graph_writes": 0 if not self.enable_graph_writes else "enabled",
        }

    def _choose(
        self, workspace: Path, loop: dict[str, Any], i: int
    ) -> tuple[str | None, str, float | int, str]:
        leaves = self.platform.dag.leaves()
        parent = (leaves[i % len(leaves)]["hash"] if leaves else loop.get("best_commit"))
        axis = HPARAM_NAMES[i % len(HPARAM_NAMES)]
        grid = _STEPS[axis]
        value = grid[(i // len(HPARAM_NAMES)) % len(grid)]
        # surprise: prefer a leaf with few children
        if leaves:
            scored = []
            for leaf in leaves:
                kids = self.platform.dag.children(leaf["hash"])
                streak = self._lineage_reverts.get(leaf["hash"], 0)
                surprise = 0.0
                if leaf.get("metric_value") is not None and loop.get("best_metric") is not None:
                    surprise = abs(float(leaf["metric_value"]) - float(loop["best_metric"]))
                scored.append((len(kids) + streak - surprise, leaf))
            scored.sort(key=lambda x: x[0])
            parent = scored[0][1]["hash"]
        note = f"single-axis {axis}={value} from {(parent or 'best')[:12]}"
        return parent, axis, value, note

    def _hparams_of(self, text: str) -> dict[str, str]:
        return parse_hparams(text)
