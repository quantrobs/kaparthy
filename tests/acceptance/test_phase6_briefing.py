"""WP4 — leaf community briefing in the context pack (C13)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_platform.core.platform import Platform
from agentic_platform.storage.git_repo import GitWorkspace
from tests.conftest import make_control_payload


@pytest.mark.release_gate
def test_briefing_does_not_drop_essentials(platform: Platform, tmp_path: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    ws = tmp_path / "ws"
    git = GitWorkspace(ws)
    git.init()
    (ws / "note.txt").write_text("a\n", encoding="utf-8")
    h1 = git.commit("a")
    platform.dag.push(ws, agent_id="a1", hypothesis="lr=0.1 steps=40", metric_value=0.4, status="kept")
    (ws / "note.txt").write_text("b\n", encoding="utf-8")
    h2 = git.commit("b")
    platform.dag.push(ws, agent_id="a2", hypothesis="lr=0.2 steps=80", metric_value=0.3, status="reverted")
    pack = platform.dag.build_context_pack(
        leaf_hash=h2,
        token_budget=80,
        control_summary=ctl,
        best_metric=0.3,
        kept_count=1,
    )
    text = pack["text"]
    assert "protected_paths" in text or "prepare.py" in text
    assert "briefing" in pack
    assert pack["token_accounting"] == "approx_chars_div_4"
    assert pack["approx_tokens_used"] <= 80 or pack["truncated"] is True
    # distinctive seeds would be absent; none configured
    assert "7919" not in text
    _ = h1
