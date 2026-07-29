from __future__ import annotations

from typing import Any

from agentic_platform.core.ids import new_id
from agentic_platform.core.timeutil import utc_now_iso
from agentic_platform.core.validation import assert_valid
from agentic_platform.models.schemas import ControlDocument
from agentic_platform.storage.db import Database


class ControlService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data.setdefault("id", new_id("ctl_"))
        data.setdefault("version", "1")
        data.setdefault("created_at", utc_now_iso())
        # Validate via pydantic then schema
        doc = ControlDocument.model_validate(data)
        as_dict = doc.model_dump(mode="json", exclude_none=True)
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
