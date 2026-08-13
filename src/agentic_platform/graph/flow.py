"""Deterministic GraphFlow-style ranker (WP5 / C12). No process RL."""

from __future__ import annotations

from typing import Any

_EDGE_WEIGHT = {
    "PARENT_OF": 1.0,
    "EVALUATED_BY": 1.0,
    "HAS_METRIC": 1.0,
    "DERIVED_FROM": 0.6,
    "ABOUT": 0.6,
    "SUPPORTS": 0.8,
    "CONTRADICTS": 0.7,
    "PRODUCED": 0.5,
    "SUPERSEDES": 0.4,
    "RESOLVED_TO": 0.3,
    "MENTIONS": 0.3,
}

_MMR_LAMBDA = 0.4


def _cluster(node: dict[str, Any]) -> str:
    props = node.get("properties") or {}
    hyp = str(props.get("hypothesis") or node.get("label") or "")
    return hyp[:24] or node.get("id", "")


def retrieve(
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    seed_ids: list[str],
    token_budget: int,
    prefer_verified: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], int, bool]:
    """Return (included_nodes, included_edges, triples, used_chars, truncated)."""
    import json

    char_budget = token_budget * 4
    remaining = dict(nodes)
    picked: dict[str, dict[str, Any]] = {}
    for sid in seed_ids:
        if sid in remaining:
            picked[sid] = remaining.pop(sid)

    def score(nid: str) -> float:
        n = remaining[nid]
        s = 0.1
        for e in edges:
            other = None
            if e["source"] == nid and e["target"] in picked:
                other = e["target"]
                s += _EDGE_WEIGHT.get(e["type"], 0.2)
            elif e["target"] == nid and e["source"] in picked:
                other = e["source"]
                s += _EDGE_WEIGHT.get(e["type"], 0.2)
            if other is None:
                continue
        if prefer_verified and n.get("type") == "Claim":
            prov = n.get("provenance") or {}
            if prov.get("source_ids"):
                s += 0.5
            elif prov.get("is_inference"):
                s -= 0.4
        props = n.get("properties") or {}
        if props.get("sealed"):
            s += 0.3
        # MMR diversity vs already picked clusters
        c = _cluster(n)
        if any(_cluster(p) == c for p in picked.values()):
            s *= 1.0 - _MMR_LAMBDA
        return s

    used = sum(len(json.dumps(n)) for n in picked.values())
    included_edges: list[dict[str, Any]] = []
    triples: list[str] = []

    while remaining:
        ranked = sorted(remaining.keys(), key=score, reverse=True)
        nid = ranked[0]
        n = remaining.pop(nid)
        piece_cost = len(json.dumps(n)) + 16
        if used + piece_cost > char_budget and picked:
            break
        picked[nid] = n
        used += piece_cost
        for e in edges:
            if e["source"] in picked and e["target"] in picked and e not in included_edges:
                triple = f"{e['source']}-[{e['type']}]->{e['target']}"
                cost = len(triple) + 8
                if used + cost > char_budget:
                    continue
                included_edges.append(e)
                triples.append(triple)
                used += cost

    truncated = used >= char_budget or len(picked) < len(nodes)
    return list(picked.values()), included_edges, triples, used, truncated
