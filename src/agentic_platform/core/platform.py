from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic_platform.control.service import ControlService
from agentic_platform.dag.service import DagService
from agentic_platform.eval.service import EvalService
from agentic_platform.graph.service import GraphService
from agentic_platform.loops.service import LoopService
from agentic_platform.runs.service import RunService
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

        self.runs = RunService(self.db, self.artifacts)
        self.control = ControlService(self.db)
        self.eval = EvalService(self.db, audit_hook=self._audit)
        self.graph = GraphService(
            self.db,
            budget_check=self._graph_budget,
            audit_hook=self._audit,
        )
        self.loops = LoopService(
            self.db,
            self.artifacts,
            self.control,
            audit_hook=self._audit,
        )
        self.dag = DagService(self.db, self.bare, audit_hook=self._audit)

        # Seed a default agent key for local/dev
        existing = self.db.fetchone("SELECT key FROM agent_keys WHERE agent_id = ?", ("architect",))
        if not existing:
            self.db.execute(
                "INSERT INTO agent_keys (key, agent_id) VALUES (?, ?)",
                ("architect-dev-key", "architect"),
            )

    def _audit(self, run_id: str | None, kind: str, payload: dict[str, Any]) -> None:
        self.runs.audit(run_id, kind, payload)

    def _graph_budget(self, run_id: str, writes: int) -> None:
        self.runs.consume(run_id, graph_writes=writes)

    def close(self) -> None:
        self.db.close()

    def resolve_agent(self, api_key: str | None) -> str:
        if not api_key:
            return "anonymous"
        row = self.db.fetchone("SELECT agent_id FROM agent_keys WHERE key = ?", (api_key,))
        return row["agent_id"] if row else "unknown"
