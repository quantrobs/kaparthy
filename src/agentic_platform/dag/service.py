from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from agentic_platform.core.ids import new_id
from agentic_platform.core.timeutil import utc_now_iso
from agentic_platform.core.validation import assert_valid
from agentic_platform.models.schemas import CommitNode
from agentic_platform.storage.db import Database
from agentic_platform.storage.git_repo import BareGitHub, GitWorkspace


class DagService:
    """AgentHub-style commit DAG + message board."""

    def __init__(
        self,
        db: Database,
        bare_repo: BareGitHub,
        audit_hook: Callable[[str | None, str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.db = db
        self.bare = bare_repo
        self.audit_hook = audit_hook or (lambda *a, **k: None)

    def push(
        self,
        workspace_path: str | Path,
        agent_id: str,
        hypothesis: str | None = None,
        metric_name: str | None = None,
        metric_value: float | None = None,
        status: str = "evidence",
        message: str | None = None,
    ) -> dict[str, Any]:
        workspace = Path(workspace_path)
        git = GitWorkspace(workspace)
        commit_hash = self.bare.receive_from_workspace(workspace)
        parents = self._parents_of(workspace, commit_hash)
        node = {
            "hash": commit_hash,
            "parents": parents,
            "agent_id": agent_id,
            "hypothesis": hypothesis,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "status": status,
            "message": message,
            "created_at": utc_now_iso(),
            "board_post_ids": [],
        }
        CommitNode.model_validate(node)
        assert_valid("CommitNode", {k: v for k, v in node.items() if v is not None})

        existing = self.db.fetchone("SELECT hash FROM commit_nodes WHERE hash = ?", (commit_hash,))
        if existing:
            self.db.execute(
                "UPDATE commit_nodes SET parents = ?, agent_id = ?, payload = ?, status = ? WHERE hash = ?",
                (
                    self.db.dumps(parents),
                    agent_id,
                    self.db.dumps(node),
                    status,
                    commit_hash,
                ),
            )
        else:
            self.db.execute(
                "INSERT INTO commit_nodes (hash, parents, agent_id, payload, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    commit_hash,
                    self.db.dumps(parents),
                    agent_id,
                    self.db.dumps(node),
                    status,
                    node["created_at"],
                ),
            )
        self.audit_hook(None, "dag.push", node)
        return node

    def register_node(self, node: dict[str, Any]) -> dict[str, Any]:
        """Register metadata without requiring a workspace push (tests / multi-agent)."""
        data = dict(node)
        data.setdefault("created_at", utc_now_iso())
        data.setdefault("board_post_ids", [])
        CommitNode.model_validate(data)
        assert_valid("CommitNode", {k: v for k, v in data.items() if v is not None})
        self.db.execute(
            "INSERT OR REPLACE INTO commit_nodes (hash, parents, agent_id, payload, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                data["hash"],
                self.db.dumps(data.get("parents") or []),
                data["agent_id"],
                self.db.dumps(data),
                data["status"],
                data["created_at"],
            ),
        )
        return data

    def fetch(self, commit_hash: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT payload FROM commit_nodes WHERE hash = ?", (commit_hash,))
        if row:
            return self.db.loads(row["payload"])
        # Prefix match
        rows = self.db.fetchall("SELECT payload FROM commit_nodes WHERE hash LIKE ?", (f"{commit_hash}%",))
        if len(rows) == 1:
            return self.db.loads(rows[0]["payload"])
        return None

    def children(self, commit_hash: str) -> list[dict[str, Any]]:
        full = self._resolve_hash(commit_hash)
        out = []
        for row in self.db.fetchall("SELECT payload FROM commit_nodes"):
            node = self.db.loads(row["payload"])
            if full in (node.get("parents") or []):
                out.append(node)
        return out

    def leaves(self) -> list[dict[str, Any]]:
        all_nodes = [self.db.loads(r["payload"]) for r in self.db.fetchall("SELECT payload FROM commit_nodes")]
        parents_of_someone = set()
        for n in all_nodes:
            for p in n.get("parents") or []:
                parents_of_someone.add(p)
        return [n for n in all_nodes if n["hash"] not in parents_of_someone]

    def lineage(self, commit_hash: str) -> list[dict[str, Any]]:
        path: list[dict[str, Any]] = []
        current = self._resolve_hash(commit_hash)
        seen: set[str] = set()
        while current and current not in seen:
            seen.add(current)
            node = self.fetch(current)
            if not node:
                break
            path.append(node)
            parents = node.get("parents") or []
            current = parents[0] if parents else None
        return path

    def diff(self, a: str, b: str) -> dict[str, Any]:
        na = self.fetch(a)
        nb = self.fetch(b)
        return {
            "a": na,
            "b": nb,
            "metric_delta": self._metric_delta(na, nb),
            "same_agent": bool(na and nb and na.get("agent_id") == nb.get("agent_id")),
        }

    def board_post(
        self,
        agent_id: str,
        body: str,
        commit_hash: str | None = None,
    ) -> dict[str, Any]:
        post = {
            "id": new_id("post_"),
            "agent_id": agent_id,
            "commit_hash": commit_hash,
            "body": body,
            "created_at": utc_now_iso(),
        }
        self.db.execute(
            "INSERT INTO board_posts (id, agent_id, commit_hash, body, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                post["id"],
                agent_id,
                commit_hash,
                body,
                self.db.dumps(post),
                post["created_at"],
            ),
        )
        self.audit_hook(None, "dag.board", post)
        return post

    def board_list(self) -> list[dict[str, Any]]:
        rows = self.db.fetchall("SELECT payload FROM board_posts ORDER BY created_at")
        return [self.db.loads(r["payload"]) for r in rows]

    def checkout(self, commit_hash: str, dest: Path) -> Path:
        full = self._resolve_hash(commit_hash)
        if not full:
            raise ValueError(f"unknown commit: {commit_hash}")
        if self.bare.has_commit(full):
            self.bare.checkout_to(full, dest)
        return dest

    def _resolve_hash(self, commit_hash: str) -> str | None:
        node = self.fetch(commit_hash)
        return node["hash"] if node else None

    def _parents_of(self, workspace: Path, commit_hash: str) -> list[str]:
        r = subprocess_parents(workspace, commit_hash)
        return r

    @staticmethod
    def _metric_delta(a: dict[str, Any] | None, b: dict[str, Any] | None) -> float | None:
        if not a or not b:
            return None
        va, vb = a.get("metric_value"), b.get("metric_value")
        if va is None or vb is None:
            return None
        return float(vb) - float(va)


def subprocess_parents(workspace: Path, commit_hash: str) -> list[str]:
    import subprocess

    r = subprocess.run(
        ["git", "rev-parse", f"{commit_hash}^@"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return []
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]
