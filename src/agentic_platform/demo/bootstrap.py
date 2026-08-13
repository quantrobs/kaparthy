"""Bootstrap a measured demo loop (DEMO-BOOT-001)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_platform.core.platform import Platform
from agentic_platform.demo.payloads import demo_control_payload


def bootstrap_demo(
    data_dir: Path,
    workspace: Path | None = None,
    agent_id: str = "demo",
    *,
    close_platform: bool = True,
) -> dict[str, Any]:
    """Create control doc + loop; seed trainer via LoopService if workspace empty.

    Requires a non-null baseline ``best_metric`` (fail loud for demos).
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    if workspace is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        workspace = data_dir / "demo_workspaces" / stamp
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    platform = Platform(data_dir)
    try:
        ctl = platform.control.create(demo_control_payload())
        loop = platform.loops.start(ctl["id"], workspace, agent_id=agent_id)
        best_metric = loop.get("best_metric")
        if best_metric is None:
            raise RuntimeError(
                "demo bootstrap failed: baseline best_metric is null "
                "(run_command did not produce a parseable val_loss)"
            )

        loop_id = loop["id"]
        result: dict[str, Any] = {
            "control_id": ctl["id"],
            "loop_id": loop_id,
            "workspace_path": str(Path(loop["workspace_path"]).resolve()),
            "best_metric": best_metric,
            "best_commit": loop.get("best_commit"),
            "agent_id": agent_id,
            "next_commands": [
                f"ah demo athlete --loop {loop_id} --max-trials 8",
                f"ah demo hostile --loop {loop_id}",
                "ah leaves",
                "ah board",
                "ah context --budget-tokens 2000",
                f"ah demo show --loop {loop_id}",
            ],
        }

        for name in ("train.py", "prepare.py", "program.md"):
            if not (workspace / name).exists():
                raise RuntimeError(f"demo bootstrap incomplete: missing {name} in {workspace}")

        return result
    finally:
        if close_platform:
            platform.close()
