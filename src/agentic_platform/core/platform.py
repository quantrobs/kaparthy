from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic_platform.control.service import ControlService
from agentic_platform.dag.service import DagService
from agentic_platform.eval.service import EvalService
from agentic_platform.graph.service import GraphService
from agentic_platform.loops.service import LoopService
from agentic_platform.runs.service import RunService
from agentic_platform.security.auth import AuthService
from agentic_platform.storage.artifacts import ArtifactStore
from agentic_platform.storage.db import Database
from agentic_platform.storage.git_repo import BareGitHub


class Platform:
    """Composition root for the five-plane architecture."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(self.data_dir / "platform.db")
        self.artifacts = ArtifactStore(self.data_dir / "artifacts")
        self.bare = BareGitHub(self.data_dir / "hub.git")
        self.auth = AuthService(self.db)
        self.auth.ensure_dev_key()

        self.runs = RunService(self.db, self.artifacts)
        self.control = ControlService(self.db)
        self.eval = EvalService(self.db, audit_hook=self._audit)
        self.graph = GraphService(
            self.db,
            budget_check=self._graph_budget,
            audit_hook=self._audit,
        )
        self.dag = DagService(self.db, self.bare, audit_hook=self._audit)
        self.loops = LoopService(
            self.db,
            self.artifacts,
            self.control,
            audit_hook=self._audit,
            dag=self.dag,
        )

    def _audit(self, run_id: str | None, kind: str, payload: dict[str, Any]) -> None:
        self.runs.audit(run_id, kind, payload)

    def _graph_budget(self, run_id: str, writes: int) -> None:
        self.runs.consume(run_id, graph_writes=writes)

    def close(self) -> None:
        self.db.close()

    def project_loop(self, loop_id: str) -> dict[str, Any]:
        from agentic_platform.graph.projector import project_loop

        loop = self.loops.get(loop_id)
        if not loop:
            raise ValueError(f"unknown loop: {loop_id}")
        budget = self.runs.create_budget({"max_graph_writes": 10_000})
        run = self.runs.create_run(loop["control_document_id"], budget["id"])
        return project_loop(self.graph, self.loops.list_trials(loop_id), run_id=run["id"])

    def resolve_agent(self, api_key: str | None) -> str:
        return self.auth.resolve(api_key)

    def health(self) -> dict[str, Any]:
        """Readiness: DB reachable, bare repo present, contracts loadable."""
        checks: dict[str, Any] = {"status": "ok", "contract": "v0.1.2", "phase": "6"}
        try:
            self.db.fetchone("SELECT 1")
            checks["db"] = "ok"
        except Exception as e:
            checks["db"] = f"fail:{e}"
            checks["status"] = "degraded"
        checks["hub"] = "ok" if self.bare.path.exists() else "missing"
        if checks["hub"] != "ok":
            checks["status"] = "degraded"
        try:
            from agentic_platform.core.validation import validate_schema

            errs = validate_schema(
                "BudgetDeclaration",
                {"id": "healthcheck"},
            )
            checks["schemas"] = "ok" if not errs else f"fail:{errs}"
        except Exception as e:
            checks["schemas"] = f"fail:{e}"
            checks["status"] = "degraded"
        return checks
