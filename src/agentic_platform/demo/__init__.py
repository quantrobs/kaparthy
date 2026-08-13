"""Demo bootstrap / hostile-reject helpers for live room scripts."""

from agentic_platform.demo.bootstrap import bootstrap_demo
from agentic_platform.demo.hostile import run_hostile_reject
from agentic_platform.demo.payloads import demo_control_payload
from agentic_platform.demo.show import show_demo

__all__ = [
    "bootstrap_demo",
    "demo_control_payload",
    "run_hostile_reject",
    "show_demo",
]
