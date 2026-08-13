from __future__ import annotations

from typing import Any

from agentic_platform.core.ids import new_id
from agentic_platform.core.timeutil import utc_now_iso
from agentic_platform.core.validation import assert_valid
from agentic_platform.models.schemas import ControlDocument
from agentic_platform.security.sandbox import SandboxError, validate_run_command
from agentic_platform.storage.db import Database


class ControlService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data.setdefault("id", new_id("ctl_"))
        data.setdefault("version", "1")
        data.setdefault("created_at", utc_now_iso())
        if not data.get("program_md"):
            data["program_md"] = self.render_program(data)
        try:
            validate_run_command(str(data.get("run_command") or ""), strict=True)
        except SandboxError as e:
            raise ValueError(f"invalid run_command: {e}") from e
        doc = ControlDocument.model_validate(data)
        as_dict = doc.model_dump(mode="json", exclude_none=True, by_alias=True)
        # Never persist/render is fine; still store seeds on the control doc
        # (they are operator-sealed). Agents see redacted views only.
        assert_valid("ControlDocument", as_dict)
        self.db.execute(
            "INSERT INTO control_documents (id, version, payload, created_at) VALUES (?, ?, ?, ?)",
            (doc.id, doc.version, self.db.dumps(as_dict), doc.created_at),
        )
        return as_dict

    def get(self, control_id: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT payload FROM control_documents WHERE id = ?", (control_id,))
        return self.db.loads(row["payload"]) if row else None

    def list(self) -> list[dict[str, Any]]:
        rows = self.db.fetchall("SELECT payload FROM control_documents ORDER BY created_at")
        return [self.db.loads(r["payload"]) for r in rows]

    @staticmethod
    def render_program(ctl: dict[str, Any]) -> str:
        """Materialize living program.md from structured control + freeform notes."""
        free = (ctl.get("program_md") or "").strip()
        header = (free + "\n\n") if free else ""
        metric = ctl.get("metric") or {}
        comparison = ctl.get("comparison") or {}
        protected = ", ".join(ctl.get("protected_paths") or []) or "(none)"
        mutable = ", ".join(ctl.get("mutable_paths") or []) or "(any non-protected)"
        kg = ctl.get("keep_gate") or {}
        keep_gate_lines = ""
        if kg:
            keep_gate_lines = (
                f"## Keep gate\n- mode: {kg.get('mode', 'single_shot')}\n"
                f"- n_min: {kg.get('n_min', '(default)')} (instance seeds are sealed)\n"
                f"- n_max: {kg.get('n_max', '(default)')}\n"
                ""
            )
        return "\n".join(
            [
                header + "# Control Program (rendered)",
                "",
                f"## Objective\n{ctl.get('objective', '')}",
                "",
                f"## Metric\n- name: {metric.get('name')}",
                f"- direction: {metric.get('direction')}",
                f"- parse_regex: {metric.get('parse_regex')}",
                f"- comparison: {comparison.get('function')}",
                "",
                f"## Surfaces\n- protected (never edit): {protected}",
                f"- mutable allowlist: {mutable}",
                f"- run_command: `{ctl.get('run_command')}`",
                f"- time_budget_seconds: {ctl.get('time_budget_seconds')}",
                "",
                f"## Keep criteria\n{ctl.get('keep_criteria', '')}",
                "",
                keep_gate_lines,
                f"## Escalation\n{ctl.get('escalation_criteria', '')}",
                "",
                f"## Exhaustion\n{ctl.get('exhaustion_criteria', '')}",
                "",
                "One change at a time. Revert on no improvement. Log hypothesis every trial.",
                "Never edit protected paths. Prefer small diffs.",
                "Write to the knowledge graph only if a future decision becomes cheaper.",
                "",
            ]
        )
