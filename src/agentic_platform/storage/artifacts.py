from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class ArtifactStore:
    """Immutable content-addressed artifact plane."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, data: bytes, suffix: str = "") -> str:
        digest = hashlib.sha256(data).hexdigest()
        name = f"{digest}{suffix}"
        path = self.root / name
        if not path.exists():
            path.write_bytes(data)
        return str(path)

    def put_text(self, text: str, suffix: str = ".txt") -> str:
        return self.put_bytes(text.encode("utf-8"), suffix=suffix)

    def put_json(self, obj: Any, suffix: str = ".json") -> str:
        data = json.dumps(obj, indent=2, sort_keys=True).encode("utf-8")
        return self.put_bytes(data, suffix=suffix)

    def append_ledger(self, loop_id: str, entry: dict[str, Any]) -> str:
        ledger_dir = self.root / "ledgers"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        path = ledger_dir / f"{loop_id}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
        return str(path)
