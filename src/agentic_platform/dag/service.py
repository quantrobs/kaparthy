from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from agentic_platform.core.ids import new_id
from agentic_platform.core.timeutil import utc_now_iso
from agentic_platform.core.validation import assert_valid
from agentic_platform.models.schemas import CommitNode
from agentic_platform.storage.db import Database
from agentic_platform.storage.git_repo import BareGitHub, GitWorkspace


class DagService:
    """AgentHub-style commit DAG + message board. Git is authoritative for topology."""

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
        commit_hash = self.bare.receive_from_workspace(workspace)
        parents = self.bare.parents_of(commit_hash)
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
        return self._store_annotation(node)

    def register_node(self, node: dict[str, Any]) -> dict[str, Any]:
        """Annotate a commit that already exists in the bare repo (Git is truth)."""
        data = dict(node)
        commit_hash = data.get("hash")
        if not commit_hash:
            raise ValueError("hash required")

        allow_orphan = os.environ.get("AGENTIC_DAG_ALLOW_ORPHAN_META") == "1"
        if not self.bare.has_commit(commit_hash):
            if not allow_orphan:
                raise ValueError(
                    f"commit not in bare Git hub (topology must be real): {commit_hash[:12]}"
                )
        else:
            # Git wins parent disputes
            data["parents"] = self.bare.parents_of(commit_hash)

        data.setdefault("created_at", utc_now_iso())
        data.setdefault("board_post_ids", [])
        return self._store_annotation(data)

    def _store_annotation(self, data: dict[str, Any]) -> dict[str, Any]:
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
                data.get("created_at") or utc_now_iso(),
            ),
        )
        self.audit_hook(None, "dag.push", data)
        return data

    def fetch(self, commit_hash: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT payload FROM commit_nodes WHERE hash = ?", (commit_hash,))
        if row:
            return self.db.loads(row["payload"])
        rows = self.db.fetchall(
            "SELECT payload FROM commit_nodes WHERE hash LIKE ?", (f"{commit_hash}%",)
        )
        if len(rows) == 1:
            return self.db.loads(rows[0]["payload"])
        # Try bare resolve
        full = self.bare.resolve_hash(commit_hash)
        if full:
            row = self.db.fetchone("SELECT payload FROM commit_nodes WHERE hash = ?", (full,))
            if row:
                return self.db.loads(row["payload"])
        return None

    def children(self, commit_hash: str) -> list[dict[str, Any]]:
        full = self._resolve_hash(commit_hash)
        if not full:
            return []
        out = []
        for row in self.db.fetchall("SELECT payload FROM commit_nodes"):
            node = self.db.loads(row["payload"])
            parents = node.get("parents") or []
            # Prefer live Git parents when object exists
            if self.bare.has_commit(node["hash"]):
                parents = self.bare.parents_of(node["hash"])
            if full in parents:
                out.append(node)
        return out

    def leaves(self) -> list[dict[str, Any]]:
        all_nodes = [
            self.db.loads(r["payload"]) for r in self.db.fetchall("SELECT payload FROM commit_nodes")
        ]
        # Build parent set from Git when possible
        parents_of_someone: set[str] = set()
        for n in all_nodes:
            parents = n.get("parents") or []
            if self.bare.has_commit(n["hash"]):
                parents = self.bare.parents_of(n["hash"])
            for p in parents:
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
                # Synthetic minimal node from Git only
                if self.bare.has_commit(current):
                    node = {
                        "hash": current,
                        "parents": self.bare.parents_of(current),
                        "agent_id": "unknown",
                        "status": "evidence",
                    }
                else:
                    break
            path.append(node)
            if self.bare.has_commit(current):
                parents = self.bare.parents_of(current)
            else:
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

    def build_context_pack(
        self,
        leaf_hash: str | None = None,
        token_budget: int = 2000,
        control_summary: dict[str, Any] | None = None,
        best_metric: float | None = None,
        kept_count: int | None = None,
        lineage_k: int = 8,
        board_m: int = 5,
    ) -> dict[str, Any]:
        """Software 3.0 bounded context for a new agent (chars/4 token approx)."""
        char_budget = token_budget * 4
        sections: list[str] = []
        truncated = False
        control_summary = self.redact_control(control_summary)

        essentials: list[str] = [
            "CONTEXT PACK — bounded; do not assume full history.",
            f"token_accounting: approx_chars_div_4; budget={token_budget}",
        ]
        if control_summary:
            # Protected paths first so tight budgets still retain the evaluation boundary
            essentials.append(
                f"protected_paths: {control_summary.get('protected_paths')}"
            )
            essentials.append(
                f"mutable_paths: {control_summary.get('mutable_paths')}"
            )
            essentials.append(
                f"metric: {control_summary.get('metric')} "
                f"comparison: {control_summary.get('comparison')}"
            )
            kg = control_summary.get("keep_gate") or {}
            if kg:
                essentials.append(
                    f"keep_gate.mode: {kg.get('mode', 'single_shot')} seeds=sealed"
                )
            essentials.append(
                "CONTROL: "
                + json.dumps(
                    {
                        "objective": control_summary.get("objective"),
                        "run_command": control_summary.get("run_command"),
                    },
                    sort_keys=True,
                )
            )
        if best_metric is not None:
            essentials.append(f"BEST_METRIC: {best_metric} kept_count={kept_count}")

        leaf = leaf_hash
        if not leaf:
            leaves = self.leaves()
            if leaves:
                # Prefer annotated best metric leaf
                leaf = leaves[0]["hash"]
        if leaf:
            node = self.fetch(leaf)
            essentials.append(
                f"LEAF: {leaf[:12]} metric={None if not node else node.get('metric_value')} "
                f"agent={None if not node else node.get('agent_id')}"
            )

        used = sum(len(s) for s in essentials)
        sections.extend(essentials)

        briefing: list[dict[str, Any]] = []
        if leaf:
            from agentic_platform.dag.communities import brief_leaves

            briefing = brief_leaves(self.leaves())
            for cluster in briefing:
                line = f"BRIEFING {cluster['text']}"
                if used + len(line) > char_budget:
                    truncated = True
                    break
                sections.append(line)
                used += len(line)

        if leaf:
            lineage = self.lineage(leaf)[:lineage_k]
            for n in lineage:
                line = (
                    f"LINEAGE {n['hash'][:12]} agent={n.get('agent_id')} "
                    f"metric={n.get('metric_value')} status={n.get('status')} "
                    f"h={(n.get('hypothesis') or '')[:80]}"
                )
                if used + len(line) > char_budget:
                    truncated = True
                    break
                sections.append(line)
                used += len(line)

        posts = list(reversed(self.board_list()))[:board_m]
        # Prefer posts linked to lineage
        lineage_hashes = set()
        if leaf:
            lineage_hashes = {n["hash"] for n in self.lineage(leaf)[:lineage_k]}
        posts.sort(
            key=lambda p: (0 if p.get("commit_hash") in lineage_hashes else 1, p.get("created_at") or "")
        )
        for p in posts[:board_m]:
            line = f"BOARD [{p.get('agent_id')}] {p.get('body', '')[:200]}"
            if used + len(line) > char_budget:
                truncated = True
                break
            sections.append(line)
            used += len(line)

        text = "\n".join(sections)
        if len(text) > char_budget:
            text = text[:char_budget]
            truncated = True

        return {
            "text": text,
            "leaf_hash": leaf,
            "token_budget": token_budget,
            "approx_tokens_used": len(text) // 4,
            "truncated": truncated,
            "token_accounting": "approx_chars_div_4",
            "sections": len(sections),
            "briefing": briefing,
        }

    @staticmethod
    def redact_control(control_summary: dict[str, Any] | None) -> dict[str, Any] | None:
        """Strip sealed keep_gate.seeds from any agent-visible control dump."""
        if not control_summary:
            return control_summary
        out = dict(control_summary)
        kg = out.get("keep_gate")
        if isinstance(kg, dict) and "seeds" in kg:
            kg = dict(kg)
            kg.pop("seeds", None)
            kg["seeds_sealed"] = True
            out["keep_gate"] = kg
        return out

    def checkout(self, commit_hash: str, dest: Path) -> Path:
        full = self._resolve_hash(commit_hash)
        if not full:
            raise ValueError(f"unknown commit: {commit_hash}")
        if self.bare.has_commit(full):
            self.bare.checkout_to(full, dest)
        return dest

    def _resolve_hash(self, commit_hash: str) -> str | None:
        node = self.fetch(commit_hash)
        if node:
            return node["hash"]
        return self.bare.resolve_hash(commit_hash)

    @staticmethod
    def _metric_delta(a: dict[str, Any] | None, b: dict[str, Any] | None) -> float | None:
        if not a or not b:
            return None
        va, vb = a.get("metric_value"), b.get("metric_value")
        if va is None or vb is None:
            return None
        return float(vb) - float(va)
