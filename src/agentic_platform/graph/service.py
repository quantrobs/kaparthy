from __future__ import annotations

import json
from typing import Any, Callable

from agentic_platform.core.ids import new_id
from agentic_platform.core.timeutil import utc_now_iso
from agentic_platform.core.validation import assert_valid
from agentic_platform.invariants.checks import InvariantError, InvariantGuard
from agentic_platform.models.schemas import GraphUpdate
from agentic_platform.storage.db import Database


class GraphService:
    """Knowledge-graph overlay on top of work lineage."""

    def __init__(
        self,
        db: Database,
        budget_check: Callable[[str, int], None] | None = None,
        audit_hook: Callable[[str | None, str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.db = db
        self.budget_check = budget_check
        self.audit_hook = audit_hook or (lambda *a, **k: None)

    def apply_update(self, payload: dict[str, Any]) -> dict[str, Any]:
        update = GraphUpdate.model_validate(payload)
        as_dict = update.model_dump(mode="json", exclude_none=True)
        assert_valid("GraphUpdate", as_dict)

        writes = 0
        for node in as_dict.get("nodes") or []:
            InvariantGuard.require_claim_source(node)
            InvariantGuard.require_artifact_authorship(node)
            self._upsert_node(node)
            writes += 1

        for edge in as_dict.get("edges") or []:
            self._upsert_edge(edge)
            writes += 1

        for op in as_dict.get("resolution_ops") or []:
            if not op.get("reversible", True):
                raise InvariantError(9, "entity-resolution decisions must be reversible")
            self._apply_resolution(op)
            writes += 1

        if self.budget_check and as_dict.get("run_id"):
            self.budget_check(as_dict["run_id"], writes)

        result = {"applied": True, "writes": writes, "run_id": as_dict["run_id"]}
        self.audit_hook(as_dict.get("run_id"), "graph.update", result)
        return result

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        # Follow RESOLVED_TO chain
        current = node_id
        seen: set[str] = set()
        while current not in seen:
            seen.add(current)
            row = self.db.fetchone(
                "SELECT payload, active FROM graph_nodes WHERE id = ?",
                (current,),
            )
            if not row:
                return None
            if row["active"]:
                return self.db.loads(row["payload"])
            # inactive — look for RESOLVED_TO
            edge = self.db.fetchone(
                "SELECT target FROM graph_edges WHERE source = ? AND type = 'RESOLVED_TO' AND active = 1",
                (current,),
            )
            if not edge:
                return self.db.loads(row["payload"])
            current = edge["target"]
        return None

    def claim_trace(self, claim_id: str) -> dict[str, Any]:
        """Trace claim → supporting sources and commits."""
        claim = self.get_node(claim_id)
        if not claim:
            raise ValueError(f"unknown claim: {claim_id}")
        supports = self.db.fetchall(
            "SELECT payload FROM graph_edges WHERE type = 'SUPPORTS' AND target = ? AND active = 1",
            (claim_id,),
        )
        edges = [self.db.loads(r["payload"]) for r in supports]
        # also edges where claim is source SUPPORTS? usually source claim target? Convention: SUPPORTS from evidence to claim
        supports2 = self.db.fetchall(
            "SELECT payload FROM graph_edges WHERE type = 'SUPPORTS' AND source = ? AND active = 1",
            (claim_id,),
        )
        edges.extend(self.db.loads(r["payload"]) for r in supports2)

        related_ids: set[str] = set()
        for e in edges:
            related_ids.add(e["source"])
            related_ids.add(e["target"])
        related_ids.discard(claim_id)

        sources = []
        commits = []
        for nid in related_ids:
            n = self.get_node(nid)
            if not n:
                continue
            if n["type"] == "Source":
                sources.append(n)
            if n["type"] == "Commit":
                commits.append(n)

        prov = claim.get("provenance") or {}
        for sid in prov.get("source_ids") or []:
            n = self.get_node(sid)
            if n and n not in sources:
                sources.append(n)

        return {
            "claim": claim,
            "sources": sources,
            "commits": commits,
            "edges": edges,
        }

    def resolve(self, from_id: str, to_id: str, evidence: str = "", op: str = "merge") -> dict[str, Any]:
        op_doc = {
            "op": op,
            "from_id": from_id,
            "to_id": to_id,
            "evidence": evidence,
            "reversible": True,
        }
        self._apply_resolution(op_doc)
        self.audit_hook(None, "graph.resolve", op_doc)
        return op_doc

    def unmerge(self, from_id: str, to_id: str, evidence: str = "reverse false merge") -> dict[str, Any]:
        """INV-09: entity-resolution decisions are additive and reversible."""
        return self.resolve(from_id, to_id, evidence=evidence, op="unmerge")

    def subgraph(
        self,
        seed_ids: list[str],
        hops: int = 2,
        token_budget: int = 2000,
        prefer_verified: bool = True,
        query: str | None = None,
    ) -> dict[str, Any]:
        """INV-12: context is a bounded subgraph only."""
        _ = query  # v1: seed + metric proximity; query reserved for WP5 v2
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}
        frontier = list(seed_ids)

        for _ in range(max(0, hops) + 1):
            next_frontier: list[str] = []
            for nid in frontier:
                if nid in nodes:
                    continue
                n = self.get_node(nid)
                if not n:
                    continue
                if n.get("type") == "Claim" and prefer_verified:
                    # deprioritize pure inference without sources unless seed
                    prov = n.get("provenance") or {}
                    if prov.get("is_inference") and nid not in seed_ids:
                        continue
                nodes[nid] = n
                for row in self.db.fetchall(
                    "SELECT payload FROM graph_edges WHERE (source = ? OR target = ?) AND active = 1",
                    (nid, nid),
                ):
                    e = self.db.loads(row["payload"])
                    edges[e["id"]] = e
                    other = e["target"] if e["source"] == nid else e["source"]
                    if other not in nodes:
                        next_frontier.append(other)
            frontier = next_frontier

        from agentic_platform.graph.flow import retrieve

        inc_nodes, inc_edges, triples, used, truncated = retrieve(
            nodes, list(edges.values()), seed_ids, token_budget, prefer_verified
        )
        # Always include seed nodes even if budget tight
        have = {n["id"] for n in inc_nodes}
        for sid in seed_ids:
            if sid in nodes and sid not in have:
                inc_nodes.append(nodes[sid])

        return {
            "nodes": inc_nodes,
            "edges": inc_edges,
            "triples": triples,
            "edge_ids": [e["id"] for e in inc_edges],
            "token_budget": token_budget,
            "approx_tokens_used": used // 4,
            "truncated": truncated or used // 4 >= token_budget or len(inc_edges) < len(edges),
            "token_accounting": "approx_chars_div_4",
            "ranker": "graphflow-v1",
            "diversity": "mmr_hparam_cluster",
        }

    def _upsert_node(self, node: dict[str, Any]) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO graph_nodes (id, type, label, payload, active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (
                node["id"],
                node["type"],
                node.get("label"),
                self.db.dumps(node),
                utc_now_iso(),
            ),
        )

    def _upsert_edge(self, edge: dict[str, Any]) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO graph_edges (id, type, source, target, payload, active, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (
                edge["id"],
                edge["type"],
                edge["source"],
                edge["target"],
                self.db.dumps(edge),
                utc_now_iso(),
            ),
        )

    def _apply_resolution(self, op: dict[str, Any]) -> None:
        op_name = op["op"]
        from_id = op["from_id"]
        to_id = op["to_id"]
        evidence = op.get("evidence") or ""
        created = utc_now_iso()

        if op_name == "merge":
            # Mark from inactive; add RESOLVED_TO edge
            self.db.execute("UPDATE graph_nodes SET active = 0 WHERE id = ?", (from_id,))
            edge = {
                "id": new_id("e_"),
                "type": "RESOLVED_TO",
                "source": from_id,
                "target": to_id,
                "properties": {"evidence": evidence},
                "provenance": {"reversible": True},
            }
            self._upsert_edge(edge)
            self.db.execute(
                "INSERT INTO resolution_log (op, from_id, to_id, evidence, reversed, created_at) VALUES (?, ?, ?, ?, 0, ?)",
                ("merge", from_id, to_id, evidence, created),
            )
        elif op_name == "unmerge":
            self.db.execute("UPDATE graph_nodes SET active = 1 WHERE id = ?", (from_id,))
            self.db.execute(
                "UPDATE graph_edges SET active = 0 WHERE source = ? AND target = ? AND type = 'RESOLVED_TO'",
                (from_id, to_id),
            )
            self.db.execute(
                "INSERT INTO resolution_log (op, from_id, to_id, evidence, reversed, created_at) VALUES (?, ?, ?, ?, 1, ?)",
                ("unmerge", from_id, to_id, evidence, created),
            )
            # mark prior merges reversed
            self.db.execute(
                "UPDATE resolution_log SET reversed = 1 WHERE op = 'merge' AND from_id = ? AND to_id = ?",
                (from_id, to_id),
            )
        else:
            raise InvariantError(9, f"unknown resolution op: {op_name}")
