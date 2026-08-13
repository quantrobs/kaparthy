from __future__ import annotations

from pathlib import Path

import pytest

from agentic_platform.core.platform import Platform


@pytest.fixture()
def platform(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Platform:
    data = tmp_path / "data"
    monkeypatch.setenv("AGENTIC_DATA", str(data))
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("AGENTIC_ROOT", str(root))
    # Never allow orphan DAG metadata in tests unless a test opts in
    monkeypatch.delenv("AGENTIC_DAG_ALLOW_ORPHAN_META", raising=False)
    monkeypatch.setenv("AGENTIC_REQUIRE_AUTH", "0")
    # Allow tests to construct Platform before flipping auth flags per-test
    monkeypatch.delenv("AGENTIC_ALLOW_ARBITRARY_RUN_CMD", raising=False)
    p = Platform(data)
    yield p
    p.close()


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Empty workspace — LoopService seeds the real demo trainer."""
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


def make_control_payload() -> dict:
    """Test helper — same shape as demo; created_by remains architect for tests."""
    from agentic_platform.demo.payloads import demo_control_payload

    payload = demo_control_payload()
    payload["created_by"] = "architect"
    return payload
