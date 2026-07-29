"""§8 Acceptance — Knowledge Graph."""

from __future__ import annotations

from agentic_platform.core.platform import Platform
from tests.conftest import make_control_payload


def test_claim_traces_to_sources_and_commits(platform: Platform) -> None:
    ctl = platform.control.create(make_control_payload())
    budget = platform.runs.create_budget({"max_graph_writes": 100})
    run = platform.runs.create_run(ctl["id"], budget["id"])

    update = {
        "run_id": run["id"],
        "agent_id": "graph-agent",
        "nodes": [
            {
                "id": "src_paper",
                "type": "Source",
                "label": "Karpathy autoresearch",
                "properties": {"uri": "https://github.com/karpathy/autoresearch"},
            },
            {
                "id": "commit_abc",
                "type": "Commit",
                "label": "kept optimization",
                "properties": {"hash": "abc"},
            },
            {
                "id": "claim_1",
                "type": "Claim",
                "label": "QK norm helps",
                "provenance": {"source_ids": ["src_paper"], "run_id": run["id"], "is_inference": False},
            },
        ],
        "edges": [
            {
                "id": "e1",
                "type": "SUPPORTS",
                "source": "src_paper",
                "target": "claim_1",
            },
            {
                "id": "e2",
                "type": "SUPPORTS",
                "source": "commit_abc",
                "target": "claim_1",
            },
            {
                "id": "e3",
                "type": "ABOUT",
                "source": "claim_1",
                "target": "commit_abc",
            },
        ],
    }
    platform.graph.apply_update(update)
    trace = platform.graph.claim_trace("claim_1")
    assert trace["claim"]["id"] == "claim_1"
    assert any(s["id"] == "src_paper" for s in trace["sources"])
    assert any(c["id"] == "commit_abc" for c in trace["commits"])


def test_false_entity_merge_is_reversible(platform: Platform) -> None:
    ctl = platform.control.create(make_control_payload())
    budget = platform.runs.create_budget({"max_graph_writes": 50})
    run = platform.runs.create_run(ctl["id"], budget["id"])

    platform.graph.apply_update(
        {
            "run_id": run["id"],
            "agent_id": "resolver",
            "nodes": [
                {"id": "ent_edwin", "type": "Entity", "label": "Edwin Aldrin"},
                {"id": "ent_buzz", "type": "Entity", "label": "Buzz Aldrin"},
            ],
            "edges": [],
        }
    )
    platform.graph.resolve("ent_edwin", "ent_buzz", evidence="alias")
    # inactive alias resolves to canonical
    resolved = platform.graph.get_node("ent_edwin")
    assert resolved is not None
    assert resolved["id"] == "ent_buzz"

    platform.graph.unmerge("ent_edwin", "ent_buzz", evidence="false merge")
    restored = platform.graph.get_node("ent_edwin")
    assert restored is not None
    assert restored["id"] == "ent_edwin"
    assert restored["label"] == "Edwin Aldrin"


def test_subgraph_respects_token_budget(platform: Platform) -> None:
    ctl = platform.control.create(make_control_payload())
    budget = platform.runs.create_budget({"max_graph_writes": 500})
    run = platform.runs.create_run(ctl["id"], budget["id"])

    nodes = []
    edges = []
    for i in range(30):
        nodes.append(
            {
                "id": f"n{i}",
                "type": "Entity",
                "label": f"Entity number {i} with padding " + ("x" * 40),
            }
        )
        if i > 0:
            edges.append(
                {
                    "id": f"e{i}",
                    "type": "ABOUT",
                    "source": f"n{i-1}",
                    "target": f"n{i}",
                }
            )
    platform.graph.apply_update(
        {"run_id": run["id"], "agent_id": "g", "nodes": nodes, "edges": edges}
    )

    small = platform.graph.subgraph(seed_ids=["n0"], hops=10, token_budget=50)
    assert small["approx_tokens_used"] <= 50 or small["truncated"] is True
    assert "n0" in {n["id"] for n in small["nodes"]}
    # under tight budget, cannot include entire chain
    assert len(small["edges"]) < len(edges)
