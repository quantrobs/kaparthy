from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer

from agentic_platform.core.paths import default_data_dir
from agentic_platform.core.platform import Platform

app = typer.Typer(help="ah — AgentHub / Agentic Platform CLI", no_args_is_help=True)


def _platform() -> Platform:
    return Platform(Path(os.environ.get("AGENTIC_DATA", default_data_dir())))


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


if __name__ == "__main__":
    app()
