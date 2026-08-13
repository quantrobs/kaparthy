"""WP2 — frontier fingerprint filter (C4)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from agentic_platform.core.platform import Platform
from tests.conftest import make_control_payload


def _set(workspace: Path, lr: float, steps: int) -> str:
    text = (workspace / "train.py").read_text(encoding="utf-8")
    text = re.sub(r"^LR\s*=\s*[^\n]+", f"LR = {lr}", text, flags=re.M)
    text = re.sub(r"^STEPS\s*=\s*[^\n]+", f"STEPS = {steps}", text, flags=re.M)
    return text


@pytest.mark.release_gate
def test_duplicate_hparams_rejected(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    content = _set(workspace, 0.2, 80)
    first = platform.loops.propose_trial(
        loop["id"], agent_id="a", hypothesis="lr=0.2 steps=80", file_edits={"train.py": content}
    )
    assert first["status"] in ("kept", "reverted")
    assert first.get("commit_hash")
    second = platform.loops.propose_trial(
        loop["id"], agent_id="a", hypothesis="repeat", file_edits={"train.py": content}
    )
    assert second["status"] == "rejected"
    assert "duplicate_of" in (second.get("error") or "")
    assert second.get("commit_hash") is None
