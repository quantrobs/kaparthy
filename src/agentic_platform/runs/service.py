from __future__ import annotations

from typing import Any

from agentic_platform.core.ids import new_id
from agentic_platform.core.timeutil import utc_now_iso
from agentic_platform.core.validation import assert_valid
from agentic_platform.invariants.checks import InvariantError, InvariantGuard
from agentic_platform.models.schemas import BudgetDeclaration, ConsumedResources, Run
from agentic_platform.storage.artifacts import ArtifactStore
from agentic_platform.storage.db import Database


class RunService:
    def __init__(self, db: Database, artifacts: ArtifactStore) -> None:
        self.db = db
        self.artifacts = artifacts

    def create_budget(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data.setdefault("id", new_id("bud_"))
        doc = BudgetDeclaration.model_validate(data)
        as_dict = doc.model_dump(mode="json", exclude_none=True)
        assert_valid("BudgetDeclaration", as_dict)
        self.db.execute(
            "INSERT INTO budgets (id, payload) VALUES (?, ?)",
            (doc.id, self.db.dumps(as_dict)),
        )
        return as_dict

    def get_budget(self, budget_id: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT payload FROM budgets WHERE id = ?", (budget_id,))
        return self.db.loads(row["payload"]) if row else None

    def create_run(self, control_document_id: str, budget_id: str) -> dict[str, Any]:
        if not self.get_budget(budget_id):
            raise ValueError(f"unknown budget: {budget_id}")
        run_id = new_id("run_")
        created = utc_now_iso()
        consumed = ConsumedResources().model_dump()
        run = {
            "id": run_id,
            "control_document_id": control_document_id,
            "budget_id": budget_id,
            "status": "running",
            "consumed": consumed,
            "audit_log_uri": None,
            "partial_result": None,
            "stop_reason": None,
            "created_at": created,
            "finished_at": None,
        }
        assert_valid("Run", {k: v for k, v in run.items() if v is not None})
        self.db.execute(
            "INSERT INTO runs (id, control_document_id, budget_id, status, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, control_document_id, budget_id, "running", self.db.dumps(run), created),
        )
        self.audit(run_id, "run.created", run)
        return run

    def get(self, run_id: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT payload FROM runs WHERE id = ?", (run_id,))
        return self.db.loads(row["payload"]) if row else None

    def audit(self, run_id: str | None, kind: str, payload: dict[str, Any]) -> None:
        self.db.execute(
            "INSERT INTO audit_events (run_id, kind, payload, created_at) VALUES (?, ?, ?, ?)",
            (run_id, kind, self.db.dumps(payload), utc_now_iso()),
        )

    def consume(self, run_id: str, **delta: Any) -> dict[str, Any]:
        run = self.get(run_id)
        if not run:
            raise ValueError(f"unknown run: {run_id}")
        if run["status"] in ("budget_exhausted", "completed", "failed", "cancelled"):
            raise InvariantError(11, f"run {run_id} is not accepting consumption ({run['status']})")

        consumed = dict(run["consumed"])
        for k, v in delta.items():
            if k not in consumed:
                raise ValueError(f"unknown consumption key: {k}")
            consumed[k] = consumed[k] + v

        budget = self.get_budget(run["budget_id"]) or {}
        stop = InvariantGuard.enforce_budget(budget, consumed)
        run["consumed"] = consumed

        if stop:
            run["status"] = "budget_exhausted"
            run["stop_reason"] = stop
            run["finished_at"] = utc_now_iso()
            run["partial_result"] = {
                "completed_work": True,
                "consumed": consumed,
                "reason": stop,
                "message": "Budget exhausted; returning structured partial result (never silent truncation).",
            }
            self.audit(run_id, "run.budget_exhausted", run)
        else:
            self.audit(run_id, "run.consume", {"delta": delta, "consumed": consumed})

        self._save(run)
        return run

    def complete(self, run_id: str, partial_result: dict[str, Any] | None = None) -> dict[str, Any]:
        run = self.get(run_id)
        if not run:
            raise ValueError(f"unknown run: {run_id}")
        if run["status"] == "budget_exhausted":
            return run
        run["status"] = "completed"
        run["finished_at"] = utc_now_iso()
        if partial_result is not None:
            run["partial_result"] = partial_result
        audit_uri = self.artifacts.put_json(self.get_audit_trail(run_id), suffix=".audit.json")
        run["audit_log_uri"] = audit_uri
        self._save(run)
        self.audit(run_id, "run.completed", run)
        return run

    def get_audit_trail(self, run_id: str) -> dict[str, Any]:
        run = self.get(run_id)
        events = self.db.fetchall(
            "SELECT run_id, kind, payload, created_at FROM audit_events WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
        trail = []
        for e in events:
            trail.append(
                {
                    "kind": e["kind"],
                    "payload": self.db.loads(e["payload"]),
                    "created_at": e["created_at"],
                }
            )
        # Reconstruct E2E chain keys
        return {
            "run": run,
            "events": trail,
            "traceability": {
                "objective": True,
                "plan": True,
                "runs": True,
                "commits": any(e["kind"].startswith("dag.") for e in trail),
                "claims": any(e["kind"].startswith("graph.") for e in trail),
                "evaluations": any(e["kind"].startswith("eval.") for e in trail),
                "budgets": True,
            },
        }

    def _save(self, run: dict[str, Any]) -> None:
        Run.model_validate(run)
        assert_valid("Run", {k: v for k, v in run.items() if v is not None})
        self.db.execute(
            "UPDATE runs SET status = ?, payload = ? WHERE id = ?",
            (run["status"], self.db.dumps(run), run["id"]),
        )
