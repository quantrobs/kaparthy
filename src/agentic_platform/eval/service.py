from __future__ import annotations

from typing import Any, Callable

from agentic_platform.core.ids import new_id
from agentic_platform.core.timeutil import utc_now_iso
from agentic_platform.core.validation import assert_valid
from agentic_platform.invariants.checks import InvariantGuard
from agentic_platform.models.schemas import EvaluationResult
from agentic_platform.storage.db import Database


class EvalService:
    def __init__(
        self,
        db: Database,
        audit_hook: Callable[[str | None, str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.db = db
        self.audit_hook = audit_hook or (lambda *a, **k: None)

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data.setdefault("id", new_id("eval_"))
        data.setdefault("created_at", utc_now_iso())
        data.setdefault("evidence_edge_ids", [])
        data.setdefault("required_fixes", [])
        InvariantGuard.require_evaluation_rubric(data)
        doc = EvaluationResult.model_validate(data)
        as_dict = doc.model_dump(mode="json", exclude_none=True)
        assert_valid("EvaluationResult", as_dict)
        self.db.execute(
            "INSERT INTO evaluations (id, payload, created_at) VALUES (?, ?, ?)",
            (doc.id, self.db.dumps(as_dict), doc.created_at),
        )
        self.audit_hook(as_dict.get("run_id"), "eval.created", as_dict)
        return as_dict

    def get(self, eval_id: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT payload FROM evaluations WHERE id = ?", (eval_id,))
        return self.db.loads(row["payload"]) if row else None

    def evaluate_metric(
        self,
        target: str,
        rubric: str,
        baseline: float | None,
        candidate: float | None,
        direction: str = "minimize",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Deterministic evaluator used by Software 3.0 control surface."""
        if candidate is None:
            decision = "fail"
            fixes = ["metric missing"]
        elif baseline is None:
            decision = "pass"
            fixes = []
        else:
            improved = candidate < baseline if direction == "minimize" else candidate > baseline
            decision = "pass" if improved else "fail"
            fixes = [] if improved else ["metric did not improve"]
        return self.create(
            {
                "decision": decision,
                "target": target,
                "rubric": rubric,
                "confidence": 1.0,
                "required_fixes": fixes,
                "run_id": run_id,
                "notes": f"baseline={baseline} candidate={candidate} direction={direction}",
            }
        )
