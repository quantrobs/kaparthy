from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from typing import Any

from agentic_platform.core.timeutil import utc_now_iso
from agentic_platform.storage.db import Database


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401) -> None:
        self.status_code = status_code
        super().__init__(message)


class AuthService:
    """Per-agent API keys with optional strict mode."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.require_auth = os.environ.get("AGENTIC_REQUIRE_AUTH", "0") == "1"
        self.reject_unknown = os.environ.get("AGENTIC_REJECT_UNKNOWN_KEYS", "1") == "1"

    def ensure_dev_key(self) -> None:
        row = self.db.fetchone("SELECT key FROM agent_keys WHERE agent_id = ?", ("architect",))
        if not row:
            self.db.execute(
                "INSERT INTO agent_keys (key, agent_id) VALUES (?, ?)",
                ("architect-dev-key", "architect"),
            )

    def create_key(self, agent_id: str, key: str | None = None) -> dict[str, Any]:
        agent_id = agent_id.strip()
        if not agent_id or len(agent_id) > 64:
            raise AuthError("invalid agent_id", 400)
        raw = key or f"ak_{secrets.token_urlsafe(24)}"
        existing = self.db.fetchone("SELECT key FROM agent_keys WHERE key = ?", (raw,))
        if existing:
            raise AuthError("key already exists", 409)
        self.db.execute(
            "INSERT INTO agent_keys (key, agent_id) VALUES (?, ?)",
            (raw, agent_id),
        )
        return {
            "agent_id": agent_id,
            "key": raw,
            "created_at": utc_now_iso(),
            "note": "store once; not retrievable later in hashed deployments",
        }

    def revoke_key(self, key: str) -> bool:
        cur = self.db.execute("DELETE FROM agent_keys WHERE key = ?", (key,))
        return cur.rowcount > 0

    def resolve(self, api_key: str | None) -> str:
        if not api_key:
            if self.require_auth:
                raise AuthError("X-Agent-Key required")
            return "anonymous"
        row = self.db.fetchone("SELECT agent_id FROM agent_keys WHERE key = ?", (api_key,))
        if row:
            return row["agent_id"]
        if self.require_auth or self.reject_unknown:
            raise AuthError("invalid agent key")
        return "unknown"

    def list_agents(self) -> list[dict[str, str]]:
        rows = self.db.fetchall("SELECT agent_id, key FROM agent_keys ORDER BY agent_id")
        # Never return full keys in list — fingerprint only
        out = []
        for r in rows:
            fp = hashlib.sha256(r["key"].encode()).hexdigest()[:12]
            out.append({"agent_id": r["agent_id"], "key_fingerprint": fp})
        return out

    @staticmethod
    def admin_token_ok(provided: str | None) -> bool:
        expected = os.environ.get("AGENTIC_ADMIN_TOKEN", "")
        if not expected:
            # Dev: allow admin ops with architect-dev-key header only if admin token unset
            return provided == "architect-dev-key"
        if not provided:
            return False
        return hmac.compare_digest(provided, expected)
