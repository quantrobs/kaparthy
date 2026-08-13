"""Operator snapshot for a demo loop (ah demo show)."""

from __future__ import annotations

from typing import Any

from agentic_platform.core.platform import Platform

_TALKING_POINTS = [
    "Keep requires real run_command parse (hostile metrics).",
    "Git workspace is reversible; failed trials are evidence.",
    "Context pack is bounded (approx_chars_div_4).",
    "Graph writes are off by default.",
]


def show_demo(platform: Platform, loop_id: str, last_n: int = 8) -> dict[str, Any]:
    loop = platform.loops.get(loop_id)
    if not loop:
        raise ValueError(f"unknown loop: {loop_id}")

    trials = platform.loops.list_trials(loop_id)
    recent = trials[-last_n:] if trials else []
    best = platform.loops.best(loop_id)
    leaves = platform.dag.leaves()
    board = platform.dag.board_list()

    return {
        "loop_id": loop_id,
        "control_document_id": loop.get("control_document_id"),
        "workspace_path": loop.get("workspace_path"),
        "status": loop.get("status"),
        "best": best,
        "trial_count": len(trials),
        "recent_statuses": [t.get("status") for t in recent],
        "leaf_count": len(leaves),
        "board_post_count": len(board),
        "talking_points": list(_TALKING_POINTS),
        "not_demoed": [
            "Full budget/run audit (see tests/acceptance/test_section8_e2e.py)",
            "Knowledge-graph writes (use --enable-graph-writes on athlete)",
            "Production auth (AGENTIC_REQUIRE_AUTH=1)",
        ],
    }
