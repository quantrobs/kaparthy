from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agentic_platform.core.platform import Platform

# Search space for train.py hyperparameters (no LLM required)
_LR_GRID = [0.01, 0.03, 0.05, 0.08, 0.1, 0.15, 0.2]
_STEPS_GRID = [20, 40, 60, 80, 120]
_HIDDEN_GRID = [4, 8, 12, 16]
_L2_GRID = [0.0, 1e-4, 1e-3]


class SimpleLoopAgent:
    """Dumb heuristic agent: read program.md + context, mutate train.py, trial, board."""

    def __init__(
        self,
        platform: Platform,
        loop_id: str,
        agent_id: str = "simple-agent",
        enable_graph_writes: bool = False,
    ) -> None:
        self.platform = platform
        self.loop_id = loop_id
        self.agent_id = agent_id
        self.enable_graph_writes = enable_graph_writes
        self._trial_index = 0
        self._revert_streak = 0

    def run(self, max_trials: int = 8) -> dict[str, Any]:
        loop = self.platform.loops.get(self.loop_id)
        if not loop:
            raise ValueError(f"unknown loop: {self.loop_id}")
        ctl = self.platform.control.get(loop["control_document_id"])
        workspace = Path(loop["workspace_path"])

        history: list[dict[str, Any]] = []
        start_best = loop.get("best_metric")

        for i in range(max_trials):
            self._trial_index = i
            pack = self.platform.dag.build_context_pack(
                leaf_hash=loop.get("best_commit"),
                token_budget=1500,
                control_summary=ctl,
                best_metric=loop.get("best_metric"),
                kept_count=len(
                    [t for t in self.platform.loops.list_trials(self.loop_id) if t["status"] == "kept"]
                ),
            )
            program = ""
            program_path = workspace / "program.md"
            if program_path.exists():
                program = program_path.read_text(encoding="utf-8")[:4000]

            edits = self._propose_edit(workspace, i)
            hypothesis = f"heuristic trial {i}: {edits.get('_note', 'mutate hparams')}"
            edits.pop("_note", None)

            trial = self.platform.loops.propose_trial(
                self.loop_id,
                agent_id=self.agent_id,
                hypothesis=hypothesis,
                file_edits=edits if edits else None,
            )
            history.append(trial)

            # Push kept/evidence commits to hub when present
            if trial.get("commit_hash") and trial["status"] in ("kept", "reverted"):
                # After revert, commit may have been reset — only push kept
                if trial["status"] == "kept":
                    try:
                        self.platform.dag.push(
                            workspace,
                            agent_id=self.agent_id,
                            hypothesis=hypothesis,
                            metric_name=trial.get("metric_name"),
                            metric_value=trial.get("metric_value"),
                            status="kept",
                        )
                    except Exception:
                        pass

            if trial["status"] == "kept":
                self._revert_streak = 0
            elif trial["status"] == "reverted":
                self._revert_streak += 1
            if self._revert_streak >= 3:
                self.platform.dag.board_post(
                    self.agent_id,
                    f"3 consecutive reverts. last={trial.get('metric_value')} "
                    f"best={self.platform.loops.get(self.loop_id).get('best_metric')} "
                    f"context_tokens~{pack.get('approx_tokens_used')}",
                    commit_hash=loop.get("best_commit"),
                )
                self._revert_streak = 0

            # Graph writes off by default (C7)
            if self.enable_graph_writes:
                pass  # explicit no-op unless future expansion

            loop = self.platform.loops.get(self.loop_id) or loop
            _ = program  # read for Software 3.0 discipline; heuristic does not need NLP

        end = self.platform.loops.get(self.loop_id) or loop
        return {
            "loop_id": self.loop_id,
            "trials": len(history),
            "statuses": [t["status"] for t in history],
            "start_best": start_best,
            "end_best": end.get("best_metric"),
            "improved": (
                start_best is not None
                and end.get("best_metric") is not None
                and float(end["best_metric"]) < float(start_best)
            ),
            "kept": sum(1 for t in history if t["status"] == "kept"),
            "graph_writes": 0 if not self.enable_graph_writes else "enabled",
        }

    def _propose_edit(self, workspace: Path, i: int) -> dict[str, str]:
        train_path = workspace / "train.py"
        if not train_path.exists():
            return {}
        text = train_path.read_text(encoding="utf-8")
        lr = _LR_GRID[i % len(_LR_GRID)]
        steps = _STEPS_GRID[(i // 2) % len(_STEPS_GRID)]
        hidden = _HIDDEN_GRID[(i // 3) % len(_HIDDEN_GRID)]
        l2 = _L2_GRID[(i // 4) % len(_L2_GRID)]

        def sub(name: str, value: float | int, src: str) -> str:
            return re.sub(
                rf"^({name}\s*=\s*)[^\n]+",
                rf"\g<1>{value}",
                src,
                count=1,
                flags=re.MULTILINE,
            )

        new = text
        new = sub("LR", lr, new)
        new = sub("STEPS", steps, new)
        new = sub("HIDDEN", hidden, new)
        new = sub("L2", l2, new)
        if new == text:
            # Force a comment bump so git sees a change even if grids collide
            new = text.rstrip() + f"\n# agent touch {i}\n"
        return {
            "train.py": new,
            "_note": f"LR={lr} STEPS={steps} HIDDEN={hidden} L2={l2}",
        }
