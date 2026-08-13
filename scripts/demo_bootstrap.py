#!/usr/bin/env python3
"""Thin runner: bootstrap a demo measured loop; print JSON (DEMO-BOOT-001)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from agentic_platform.core.paths import default_data_dir
from agentic_platform.demo.bootstrap import bootstrap_demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Agentic Platform demo loop")
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="AGENTIC_DATA directory (default: env or repo data/)",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace path (default: {data}/demo_workspaces/<stamp>/)",
    )
    parser.add_argument("--agent", default="demo", help="agent_id for loop start")
    args = parser.parse_args(argv)

    data_dir = args.data or Path(os.environ.get("AGENTIC_DATA", default_data_dir()))
    result = bootstrap_demo(data_dir, workspace=args.workspace, agent_id=args.agent)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
