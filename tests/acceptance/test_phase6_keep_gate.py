"""WP1 — sealed paired keep-gate (C6 + C7) + C10 last-match."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from agentic_platform.core.platform import Platform
from tests.conftest import make_control_payload

SEEDS = [7919, 7933, 7949]


def _pace_payload() -> dict:
    p = make_control_payload()
    p["keep_gate"] = {
        "mode": "paired_pace",
        "n_min": 3,
        "n_max": 3,
        "alpha": 0.2,
        "lambda": 0.8,
        "seeds": SEEDS,
        "seed_env": "AGENTIC_EVAL_SEED",
    }
    return p


def _script(body: str) -> str:
    return "import os\n" + body + "\n"


@pytest.mark.release_gate
def test_fake_print_uses_last_match(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(make_control_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    text = (workspace / "train.py").read_text(encoding="utf-8")
    cheated = text.replace(
        "def main() -> None:",
        'def main() -> None:\n    print("val_loss=0.0")',
        1,
    )
    t = platform.loops.propose_trial(
        loop["id"],
        agent_id="faker",
        hypothesis="prepend fake metric",
        file_edits={"train.py": cheated},
    )
    assert t["status"] in ("kept", "reverted")
    assert t.get("metric_value") is not None
    assert t["metric_value"] != 0.0


@pytest.mark.release_gate
def test_seed_not_in_context_or_program(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(_pace_payload())
    program = ctl.get("program_md") or ""
    for s in SEEDS:
        assert str(s) not in program
    loop = platform.loops.start(ctl["id"], workspace)
    pack = platform.dag.build_context_pack(
        leaf_hash=loop.get("best_commit"),
        token_budget=400,
        control_summary=ctl,
        best_metric=loop.get("best_metric"),
        kept_count=0,
    )
    text = pack["text"]
    for s in SEEDS:
        assert str(s) not in text
    assert "seeds=sealed" in text or "keep_gate" in text


@pytest.mark.release_gate
def test_lucky_single_seed_does_not_keep(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(_pace_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    lucky = _script(
        "seed = int(os.environ.get('AGENTIC_EVAL_SEED', '0'))\n"
        "print('val_loss=0.01' if seed == 7919 else 'val_loss=9.99')"
    )
    t = platform.loops.propose_trial(
        loop["id"],
        agent_id="lucky",
        hypothesis="better on one sealed seed only",
        file_edits={"train.py": lucky},
    )
    assert t["status"] == "reverted"
    cert = t.get("keep_certificate")
    assert cert is not None
    assert cert["mode"] == "paired_pace"
    assert cert["losses"] >= 1
    assert cert.get("e_value") is not None


@pytest.mark.release_gate
def test_keep_writes_certificate(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(_pace_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    better = _script("print('val_loss=0.01')")
    t = platform.loops.propose_trial(
        loop["id"],
        agent_id="honest",
        hypothesis="strictly better on all sealed seeds",
        file_edits={"train.py": better},
    )
    assert t["status"] == "kept"
    cert = t.get("keep_certificate")
    assert cert is not None
    assert cert["mode"] == "paired_pace"
    assert cert["n_pairs"] >= 3
    assert cert["wins"] >= 3
    assert cert.get("e_value") is not None


@pytest.mark.release_gate
def test_agent_cannot_author_holdout(platform: Platform, workspace: Path) -> None:
    ctl = platform.control.create(_pace_payload())
    loop = platform.loops.start(ctl["id"], workspace)
    t = platform.loops.propose_trial(
        loop["id"],
        agent_id="rogue",
        hypothesis="author holdout",
        file_edits={"keep_gate.json": '{"seeds": [1]}'},
    )
    assert t["status"] == "rejected"
    err = t.get("error") or ""
    assert "INV-02" in err or "holdout" in err.lower() or "keep_gate" in err.lower()
    assert t.get("commit_hash") is None
