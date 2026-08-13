from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer

from agentic_platform.agents.simple_loop_agent import SimpleLoopAgent
from agentic_platform.core.paths import default_data_dir
from agentic_platform.core.platform import Platform
from agentic_platform.demo.bootstrap import bootstrap_demo
from agentic_platform.demo.hostile import run_hostile_reject
from agentic_platform.demo.show import show_demo

app = typer.Typer(help="ah — AgentHub / Agentic Platform CLI", no_args_is_help=True)
demo_app = typer.Typer(help="Live demo: bootstrap, athlete, hostile reject", no_args_is_help=True)
app.add_typer(demo_app, name="demo")


def _platform(data: Path | None = None) -> Platform:
    root = data or Path(os.environ.get("AGENTIC_DATA", default_data_dir()))
    return Platform(Path(root))


@app.command()
def push(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    agent: str = typer.Option("cli-agent", "--agent", "-a"),
    hypothesis: Optional[str] = typer.Option(None, "--hypothesis"),
    status: str = typer.Option("evidence", "--status"),
) -> None:
    """Push HEAD commit metadata to the hub."""
    p = _platform()
    node = p.dag.push(workspace, agent_id=agent, hypothesis=hypothesis, status=status)
    typer.echo(json.dumps(node, indent=2))
    p.close()


@app.command("fetch")
def fetch_cmd(commit_hash: str) -> None:
    p = _platform()
    node = p.dag.fetch(commit_hash)
    if not node:
        raise typer.Exit(code=1)
    typer.echo(json.dumps(node, indent=2))
    p.close()


@app.command()
def children(commit_hash: str) -> None:
    p = _platform()
    typer.echo(json.dumps(p.dag.children(commit_hash), indent=2))
    p.close()


@app.command()
def leaves() -> None:
    p = _platform()
    typer.echo(json.dumps(p.dag.leaves(), indent=2))
    p.close()


@app.command()
def lineage(commit_hash: str) -> None:
    p = _platform()
    typer.echo(json.dumps(p.dag.lineage(commit_hash), indent=2))
    p.close()


@app.command()
def diff(a: str, b: str) -> None:
    p = _platform()
    typer.echo(json.dumps(p.dag.diff(a, b), indent=2))
    p.close()


@app.command("board-post")
def board_post(
    body: str,
    agent: str = typer.Option("cli-agent", "--agent", "-a"),
    commit: Optional[str] = typer.Option(None, "--commit"),
) -> None:
    p = _platform()
    typer.echo(json.dumps(p.dag.board_post(agent, body, commit), indent=2))
    p.close()


@app.command("board")
def board_list() -> None:
    p = _platform()
    typer.echo(json.dumps(p.dag.board_list(), indent=2))
    p.close()


@app.command("context")
def context_cmd(
    leaf: Optional[str] = typer.Option(None, "--leaf"),
    budget: int = typer.Option(2000, "--budget-tokens"),
    control_id: Optional[str] = typer.Option(None, "--control"),
) -> None:
    """Build a bounded Software 3.0 context pack for an agent."""
    p = _platform()
    ctl = p.control.get(control_id) if control_id else None
    pack = p.dag.build_context_pack(
        leaf_hash=leaf,
        token_budget=budget,
        control_summary=ctl,
    )
    typer.echo(json.dumps(pack, indent=2))
    p.close()


@app.command("agent-run")
def agent_run(
    loop_id: str = typer.Option(..., "--loop"),
    max_trials: int = typer.Option(8, "--max-trials"),
    agent: str = typer.Option("simple-agent", "--agent", "-a"),
    enable_graph: bool = typer.Option(False, "--enable-graph-writes"),
) -> None:
    """Run the heuristic simple loop agent (no LLM required)."""
    p = _platform()
    runner = SimpleLoopAgent(
        p, loop_id=loop_id, agent_id=agent, enable_graph_writes=enable_graph
    )
    result = runner.run(max_trials=max_trials)
    typer.echo(json.dumps(result, indent=2))
    p.close()


@demo_app.command("bootstrap")
def demo_bootstrap(
    workspace: Optional[Path] = typer.Option(None, "--workspace", "-w"),
    agent: str = typer.Option("demo", "--agent", "-a"),
    data: Optional[Path] = typer.Option(None, "--data"),
) -> None:
    """Create control document + measured loop; print DemoBootstrapResult JSON."""
    data_dir = data or Path(os.environ.get("AGENTIC_DATA", default_data_dir()))
    result = bootstrap_demo(data_dir, workspace=workspace, agent_id=agent)
    typer.echo(json.dumps(result, indent=2))


@demo_app.command("hostile")
def demo_hostile(
    loop_id: str = typer.Option(..., "--loop"),
    also_protected: bool = typer.Option(False, "--also-protected"),
    agent: str = typer.Option("demo-hostile", "--agent", "-a"),
    data: Optional[Path] = typer.Option(None, "--data"),
) -> None:
    """Prove metric_override cannot keep (INV-02); optional protected-path reject."""
    p = _platform(data)
    try:
        result = run_hostile_reject(
            p, loop_id, agent_id=agent, also_protected=also_protected
        )
        typer.echo(json.dumps(result, indent=2))
        if not result.get("passed"):
            raise typer.Exit(code=1)
    finally:
        p.close()


@demo_app.command("athlete")
def demo_athlete(
    loop_id: str = typer.Option(..., "--loop"),
    max_trials: int = typer.Option(8, "--max-trials"),
    agent: str = typer.Option("simple-agent", "--agent", "-a"),
    enable_graph: bool = typer.Option(False, "--enable-graph-writes"),
    data: Optional[Path] = typer.Option(None, "--data"),
) -> None:
    """Run the heuristic athlete on a demo loop (no LLM)."""
    p = _platform(data)
    try:
        runner = SimpleLoopAgent(
            p, loop_id=loop_id, agent_id=agent, enable_graph_writes=enable_graph
        )
        result = runner.run(max_trials=max_trials)
        typer.echo(json.dumps(result, indent=2))
    finally:
        p.close()


@demo_app.command("show")
def demo_show(
    loop_id: str = typer.Option(..., "--loop"),
    data: Optional[Path] = typer.Option(None, "--data"),
) -> None:
    """Operator snapshot: best, recent trials, leaves, board, talking points."""
    p = _platform(data)
    try:
        typer.echo(json.dumps(show_demo(p, loop_id), indent=2))
    finally:
        p.close()


if __name__ == "__main__":
    app()
