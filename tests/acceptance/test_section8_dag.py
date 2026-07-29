"""§8 Acceptance — DAG."""

from __future__ import annotations

from pathlib import Path

from agentic_platform.core.platform import Platform
from agentic_platform.storage.git_repo import GitWorkspace


def _seed_workspace(path: Path, content: str) -> str:
    path.mkdir(parents=True, exist_ok=True)
    git = GitWorkspace(path)
    git.init()
    (path / "note.txt").write_text(content, encoding="utf-8")
    return git.commit(content[:40])


def test_three_concurrent_agents_divergent_children(platform: Platform, tmp_path: Path) -> None:
    root_ws = tmp_path / "root"
    root_hash = _seed_workspace(root_ws, "root\n")
    platform.dag.register_node(
        {
            "hash": root_hash,
            "parents": [],
            "agent_id": "seed",
            "status": "kept",
            "hypothesis": "root",
            "metric_value": 1.0,
        }
    )

    children_hashes = []
    for i, agent in enumerate(["alice", "bob", "carol"]):
        ws = tmp_path / f"agent_{agent}"
        # independent clone-like workspace forked from root content
        _seed_workspace(ws, "root\n")
        # make unique child commit with parent metadata pointing to root
        git = GitWorkspace(ws)
        # force parent link by resetting to root via new commit chain
        (ws / "note.txt").write_text(f"root\nchild of {agent}\n", encoding="utf-8")
        child = git.commit(f"{agent} experiment")
        node = platform.dag.register_node(
            {
                "hash": child,
                "parents": [root_hash],
                "agent_id": agent,
                "status": "evidence",
                "hypothesis": f"idea from {agent}",
                "metric_value": 0.9 - i * 0.1,
            }
        )
        children_hashes.append(node["hash"])

    kids = platform.dag.children(root_hash)
    assert {k["hash"] for k in kids} == set(children_hashes)
    assert {k["agent_id"] for k in kids} == {"alice", "bob", "carol"}

    leaf_set = {n["hash"] for n in platform.dag.leaves()}
    assert set(children_hashes).issubset(leaf_set)
    assert root_hash not in leaf_set


def test_commit_fetchable(platform: Platform, tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    h = _seed_workspace(ws, "blob\n")
    platform.dag.push(ws, agent_id="a1", hypothesis="push me", status="kept")
    fetched = platform.dag.fetch(h)
    assert fetched is not None
    assert fetched["hash"] == h
    assert fetched["agent_id"] == "a1"


def test_message_board_survives_restart(tmp_path: Path, monkeypatch) -> None:
    data = tmp_path / "data"
    monkeypatch.setenv("AGENTIC_DATA", str(data))
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("AGENTIC_ROOT", str(root))

    p1 = Platform(data)
    post = p1.dag.board_post("alice", "hypothesis: lower LR", commit_hash="abc123")
    post_id = post["id"]
    p1.close()

    p2 = Platform(data)
    posts = p2.dag.board_list()
    assert any(p["id"] == post_id for p in posts)
    assert posts[0]["body"].startswith("hypothesis")
    p2.close()
