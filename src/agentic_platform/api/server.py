from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from agentic_platform.core.paths import default_data_dir
from agentic_platform.core.platform import Platform
from agentic_platform.invariants.checks import InvariantError

_platform: Platform | None = None


def get_platform() -> Platform:
    global _platform
    if _platform is None:
        data = Path(os.environ.get("AGENTIC_DATA", default_data_dir()))
        _platform = Platform(data)
    return _platform


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agentic Research Platform",
        version="0.1.0-frozen",
        description="Control, Loops, DAG, Graph, Eval, Runs — Master Plan §5",
    )

    @app.exception_handler(InvariantError)
    async def inv_handler(_: Request, exc: InvariantError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"error": str(exc), "code": exc.code})

    @app.exception_handler(ValueError)
    async def val_handler(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "contract": "v0.1.0-frozen"}

    # --- Control ---
    @app.post("/control", status_code=201)
    def create_control(body: dict[str, Any]) -> dict[str, Any]:
        return get_platform().control.create(body)

    @app.get("/control")
    def list_control() -> list[dict[str, Any]]:
        return get_platform().control.list()

    @app.get("/control/{control_id}")
    def get_control(control_id: str) -> dict[str, Any]:
        doc = get_platform().control.get(control_id)
        if not doc:
            raise HTTPException(404, "control document not found")
        return doc

    # --- Loops ---
    @app.post("/loops", status_code=201)
    def start_loop(body: dict[str, Any], x_agent_key: str | None = Header(default=None)) -> dict[str, Any]:
        p = get_platform()
        agent = p.resolve_agent(x_agent_key)
        return p.loops.start(
            control_document_id=body["control_document_id"],
            workspace_path=body["workspace_path"],
            agent_id=body.get("agent_id") or agent,
        )

    @app.post("/loops/{loop_id}/trials", status_code=201)
    def propose_trial(
        loop_id: str,
        body: dict[str, Any],
        x_agent_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        p = get_platform()
        agent = body.get("agent_id") or p.resolve_agent(x_agent_key)
        return p.loops.propose_trial(
            loop_id=loop_id,
            agent_id=agent,
            hypothesis=body.get("hypothesis", ""),
            file_edits=body.get("file_edits"),
            simulate_crash=bool(body.get("simulate_crash", False)),
            metric_override=body.get("metric_override"),
        )

    @app.get("/loops/{loop_id}/trials")
    def list_trials(loop_id: str) -> list[dict[str, Any]]:
        return get_platform().loops.list_trials(loop_id)

    @app.get("/loops/{loop_id}/best")
    def best(loop_id: str) -> dict[str, Any]:
        return get_platform().loops.best(loop_id)

    @app.post("/loops/{loop_id}/reproduce")
    def reproduce(loop_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = body or {}
        return get_platform().loops.reproduce_metric(loop_id, body.get("commit_hash"))

    # --- DAG ---
    @app.post("/dag/push", status_code=201)
    def dag_push(body: dict[str, Any], x_agent_key: str | None = Header(default=None)) -> dict[str, Any]:
        p = get_platform()
        agent = body.get("agent_id") or p.resolve_agent(x_agent_key)
        if body.get("node"):
            return p.dag.register_node(body["node"])
        return p.dag.push(
            workspace_path=body["workspace_path"],
            agent_id=agent,
            hypothesis=body.get("hypothesis"),
            metric_name=body.get("metric_name"),
            metric_value=body.get("metric_value"),
            status=body.get("status", "evidence"),
            message=body.get("message"),
        )

    @app.get("/dag/fetch/{commit_hash}")
    def dag_fetch(commit_hash: str) -> dict[str, Any]:
        node = get_platform().dag.fetch(commit_hash)
        if not node:
            raise HTTPException(404, "commit not found")
        return node

    @app.get("/dag/children/{commit_hash}")
    def dag_children(commit_hash: str) -> list[dict[str, Any]]:
        return get_platform().dag.children(commit_hash)

    @app.get("/dag/leaves")
    def dag_leaves() -> list[dict[str, Any]]:
        return get_platform().dag.leaves()

    @app.get("/dag/lineage/{commit_hash}")
    def dag_lineage(commit_hash: str) -> list[dict[str, Any]]:
        return get_platform().dag.lineage(commit_hash)

    @app.get("/dag/diff")
    def dag_diff(a: str, b: str) -> dict[str, Any]:
        return get_platform().dag.diff(a, b)

    @app.post("/dag/board", status_code=201)
    def board_post(body: dict[str, Any], x_agent_key: str | None = Header(default=None)) -> dict[str, Any]:
        p = get_platform()
        agent = body.get("agent_id") or p.resolve_agent(x_agent_key)
        return p.dag.board_post(agent_id=agent, body=body["body"], commit_hash=body.get("commit_hash"))

    @app.get("/dag/board")
    def board_list() -> list[dict[str, Any]]:
        return get_platform().dag.board_list()

    @app.post("/dag/context")
    def dag_context(body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = body or {}
        p = get_platform()
        ctl = None
        if body.get("control_document_id"):
            ctl = p.control.get(body["control_document_id"])
        return p.dag.build_context_pack(
            leaf_hash=body.get("leaf_hash"),
            token_budget=int(body.get("token_budget", 2000)),
            control_summary=ctl,
            best_metric=body.get("best_metric"),
            kept_count=body.get("kept_count"),
        )

    # --- Graph ---
    @app.post("/graph/updates", status_code=201)
    def graph_update(body: dict[str, Any]) -> dict[str, Any]:
        return get_platform().graph.apply_update(body)

    @app.post("/graph/subgraph")
    def graph_subgraph(body: dict[str, Any]) -> dict[str, Any]:
        return get_platform().graph.subgraph(
            seed_ids=body.get("seed_ids") or [],
            hops=int(body.get("hops", 2)),
            token_budget=int(body.get("token_budget", 2000)),
            prefer_verified=bool(body.get("prefer_verified", True)),
        )

    @app.post("/graph/resolve")
    def graph_resolve(body: dict[str, Any]) -> dict[str, Any]:
        op = body.get("op", "merge")
        if op == "unmerge":
            return get_platform().graph.unmerge(body["from_id"], body["to_id"], body.get("evidence", ""))
        return get_platform().graph.resolve(body["from_id"], body["to_id"], body.get("evidence", ""), op=op)

    @app.get("/graph/claims/{claim_id}/trace")
    def claim_trace(claim_id: str) -> dict[str, Any]:
        return get_platform().graph.claim_trace(claim_id)

    # --- Eval ---
    @app.post("/eval", status_code=201)
    def create_eval(body: dict[str, Any]) -> dict[str, Any]:
        return get_platform().eval.create(body)

    @app.get("/eval/{eval_id}")
    def get_eval(eval_id: str) -> dict[str, Any]:
        doc = get_platform().eval.get(eval_id)
        if not doc:
            raise HTTPException(404, "evaluation not found")
        return doc

    # --- Runs ---
    @app.post("/runs/budgets", status_code=201)
    def create_budget(body: dict[str, Any]) -> dict[str, Any]:
        return get_platform().runs.create_budget(body)

    @app.post("/runs", status_code=201)
    def create_run(body: dict[str, Any]) -> dict[str, Any]:
        return get_platform().runs.create_run(body["control_document_id"], body["budget_id"])

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        run = get_platform().runs.get(run_id)
        if not run:
            raise HTTPException(404, "run not found")
        return run

    @app.post("/runs/{run_id}/consume")
    def consume(run_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return get_platform().runs.consume(run_id, **body)

    @app.post("/runs/{run_id}/complete")
    def complete(run_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        return get_platform().runs.complete(run_id, (body or {}).get("partial_result"))

    @app.get("/runs/{run_id}/audit")
    def audit(run_id: str) -> dict[str, Any]:
        return get_platform().runs.get_audit_trail(run_id)

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "agentic_platform.api.server:app",
        host=os.environ.get("AGENTIC_HOST", "127.0.0.1"),
        port=int(os.environ.get("AGENTIC_PORT", "8080")),
        reload=False,
    )


if __name__ == "__main__":
    main()
