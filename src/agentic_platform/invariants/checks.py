from __future__ import annotations

from pathlib import Path
from typing import Any


class InvariantError(Exception):
    def __init__(self, code: int, message: str) -> None:
        self.code = code
        super().__init__(f"INV-{code:02d}: {message}")


class InvariantGuard:
    """Enforce Master Plan §7 invariants at service boundaries."""

    MAX_CHANGED_FILES = 20
    MAX_DIFF_BYTES = 200_000

    @staticmethod
    def reject_protected_edits(changed_files: list[str], protected_paths: list[str]) -> None:
        """INV-01: Evaluation surface is never modified by agents."""
        for path in changed_files:
            norm = path.replace("\\", "/")
            for prot in protected_paths:
                p = prot.replace("\\", "/").lstrip("./")
                if norm == p or norm.startswith(p.rstrip("/") + "/"):
                    raise InvariantError(1, f"attempt to edit protected path: {path}")

    @staticmethod
    def reject_outside_mutable(
        changed_files: list[str],
        mutable_paths: list[str] | None,
    ) -> None:
        """If mutable allowlist is set, only those paths may change."""
        if not mutable_paths:
            return
        allowed = [m.replace("\\", "/").lstrip("./") for m in mutable_paths]
        for path in changed_files:
            norm = path.replace("\\", "/").lstrip("./")
            ok = any(
                norm == a or norm.startswith(a.rstrip("/") + "/") for a in allowed
            )
            if not ok:
                raise InvariantError(1, f"edit outside mutable_paths: {path}")

    @staticmethod
    def reject_oversized_diff(changed_files: list[str], total_bytes: int) -> None:
        if len(changed_files) > InvariantGuard.MAX_CHANGED_FILES:
            raise InvariantError(
                1,
                f"too many changed files: {len(changed_files)} > {InvariantGuard.MAX_CHANGED_FILES}",
            )
        if total_bytes > InvariantGuard.MAX_DIFF_BYTES:
            raise InvariantError(
                1,
                f"diff too large: {total_bytes} > {InvariantGuard.MAX_DIFF_BYTES} bytes",
            )

    @staticmethod
    def reject_metric_override_for_keep(metric_override: float | None) -> None:
        """INV-02: metric_override can never produce a kept trial."""
        if metric_override is not None:
            raise InvariantError(2, "metric_override cannot keep (hostile evaluation)")

    @staticmethod
    def require_metric_improvement(
        direction: str,
        comparison: str,
        baseline: float | None,
        candidate: float | None,
        epsilon: float | None = None,
    ) -> bool:
        """INV-02: kept commits must satisfy comparison function."""
        if candidate is None:
            return False
        if baseline is None:
            return True
        if comparison == "strictly_better":
            return candidate < baseline if direction == "minimize" else candidate > baseline
        if comparison == "better_or_equal":
            return candidate <= baseline if direction == "minimize" else candidate >= baseline
        if comparison == "within_epsilon":
            eps = epsilon if epsilon is not None else 0.0
            return abs(candidate - baseline) <= eps
        raise InvariantError(2, f"unknown comparison function: {comparison}")

    @staticmethod
    def require_runnable(workspace: Path) -> None:
        if not workspace.exists():
            raise InvariantError(3, f"workspace missing: {workspace}")

    @staticmethod
    def require_claim_source(node: dict[str, Any]) -> None:
        if node.get("type") != "Claim":
            return
        prov = node.get("provenance") or {}
        sources = prov.get("source_ids") or []
        if not sources and not prov.get("is_inference"):
            raise InvariantError(5, f"claim {node.get('id')} lacks source or inference mark")

    @staticmethod
    def require_artifact_authorship(node: dict[str, Any]) -> None:
        if node.get("type") != "Artifact":
            return
        props = node.get("properties") or {}
        prov = node.get("provenance") or {}
        if not props.get("version"):
            raise InvariantError(6, f"artifact {node.get('id')} missing version")
        if not prov.get("run_id") and not props.get("agent_run_id"):
            raise InvariantError(6, f"artifact {node.get('id')} missing AgentRun")

    @staticmethod
    def require_evaluation_rubric(eval_doc: dict[str, Any]) -> None:
        if not eval_doc.get("rubric"):
            raise InvariantError(7, "evaluation missing rubric")

    @staticmethod
    def enforce_budget(budget: dict[str, Any], consumed: dict[str, Any]) -> str | None:
        mapping = [
            ("max_model_calls", "model_calls", "model_calls"),
            ("max_sub_agents", "sub_agents", "sub_agents"),
            ("max_tokens", "tokens", "tokens"),
            ("max_wall_clock_seconds", "wall_clock_seconds", "wall_clock"),
            ("max_cost_usd", "cost_usd", "cost"),
            ("max_graph_writes", "graph_writes", "graph_writes"),
        ]
        for bkey, ckey, label in mapping:
            limit = budget.get(bkey)
            if limit is None:
                continue
            if consumed.get(ckey, 0) > limit:
                return f"budget_exhausted:{label}"
        return None
