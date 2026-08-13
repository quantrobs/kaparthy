"""Leaf community summaries (WP4 / C13). Template only — not Claims."""

from __future__ import annotations

from typing import Any


def _cluster_id(node: dict[str, Any]) -> str:
    h = (node.get("hypothesis") or "").lower()
    # Prefer explicit hparam tokens; fall back to hypothesis prefix.
    for token in ("lr=", "steps=", "hidden=", "l2="):
        if token in h:
            break
    key_parts = []
    for name in ("lr", "steps", "hidden", "l2"):
        import re

        m = re.search(rf"{name}\s*=\s*([0-9.eE+-]+)", h)
        if m:
            key_parts.append(f"{name}{m.group(1)}")
    if key_parts:
        return "_".join(key_parts[:3]) or "misc"
    return (node.get("status") or "evidence") + ":" + (h[:24] or "empty")


def brief_leaves(leaves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for node in leaves[:64]:
        groups.setdefault(_cluster_id(node), []).append(node)

    out: list[dict[str, Any]] = []
    for cid, members in groups.items():
        metrics = [float(n["metric_value"]) for n in members if n.get("metric_value") is not None]
        kept = sum(1 for n in members if n.get("status") == "kept")
        reverted = sum(1 for n in members if n.get("status") == "reverted")
        best = min(metrics) if metrics else None
        best_hash = None
        if best is not None:
            for n in members:
                if n.get("metric_value") is not None and float(n["metric_value"]) == best:
                    best_hash = n["hash"]
                    break
        last = members[-1]
        exhausted = reverted >= 3 and kept == 0
        text = (
            f"CLUSTER {cid} n={len(members)} "
            f"best={best} @ {(best_hash or '')[:12]} "
            f"kept={kept} reverted={reverted} "
            f"last={(last.get('hypothesis') or '')[:48]!r} "
            f"status={last.get('status')} exhausted={str(exhausted).lower()}"
        )
        out.append(
            {
                "cluster_id": cid,
                "n": len(members),
                "best_metric": best,
                "best_hash": best_hash,
                "kept": kept,
                "reverted": reverted,
                "exhausted": exhausted,
                "text": text,
            }
        )
    out.sort(key=lambda c: (c["best_metric"] is None, c["best_metric"] if c["best_metric"] is not None else 0))
    return out
