"""Context pack — Software 3.0 bounded context."""

from __future__ import annotations

from pathlib import Path

from agentic_platform.core.platform import Platform
from agentic_platform.storage.git_repo import GitWorkspace
from tests.conftest import make_control_payload


def test_context_pack_includes_essentials_and_budget(platform: Platform, tmp_path: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    ws = tmp_path / "ws"
    git = GitWorkspace(ws)
    git.init()
    (ws / "note.txt").write_text("a\n", encoding="utf-8")
    h = git.commit("a")
    platform.dag.push(ws, agent_id="a1", hypothesis="try lr", metric_value=0.5, status="kept")
    platform.dag.board_post("a1", "LR 0.2 diverged", commit_hash=h)

    pack = platform.dag.build_context_pack(
        leaf_hash=h,
        token_budget=80,
        control_summary=ctl,
        best_metric=0.5,
        kept_count=1,
    )
    assert pack["token_accounting"] == "approx_chars_div_4"
    assert pack["approx_tokens_used"] <= 80 or pack["truncated"] is True
    text = pack["text"]
    assert "CONTROL" in text or "protected" in text.lower() or "val_loss" in text
    assert "protected_paths" in text or "prepare.py" in text
    assert pack["truncated"] is True or pack["approx_tokens_used"] <= 80
