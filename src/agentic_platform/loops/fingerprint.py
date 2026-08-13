"""Frontier fingerprints for SemDeDup-style reject-before-commit (C4)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

HPARAM_NAMES = ("LR", "STEPS", "HIDDEN", "L2")
_ASSIGN = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=\s*([^\n#]+)", re.MULTILINE)


def parse_hparams(text: str) -> dict[str, str]:
    found = {m.group(1): m.group(2).strip() for m in _ASSIGN.finditer(text)}
    return {name: found[name] for name in HPARAM_NAMES if name in found}


def structural_hash(text: str) -> str:
    stripped = text
    for name in HPARAM_NAMES:
        stripped = re.sub(rf"^{name}\s*=\s*[^\n]+\n?", "", stripped, flags=re.MULTILINE)
    stripped = re.sub(r"#.*", "", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return hashlib.sha256(stripped.encode("utf-8")).hexdigest()[:16]


def fingerprint_text(text: str) -> str:
    hp = parse_hparams(text)
    hp_part = ",".join(f"{k}={hp.get(k, '')}" for k in HPARAM_NAMES)
    return f"{hp_part}|{structural_hash(text)}"


def fingerprint_workspace(workspace: Path) -> str | None:
    train = Path(workspace) / "train.py"
    if not train.is_file():
        return None
    return fingerprint_text(train.read_text(encoding="utf-8"))


def cluster_key(text: str) -> str:
    """Coarse neighborhood for GraphRAG-style leaf briefing (WP4)."""
    hp = parse_hparams(text)
    try:
        lr = float(hp.get("LR", "0"))
    except ValueError:
        lr = 0.0
    try:
        steps = int(float(hp.get("STEPS", "0")))
    except ValueError:
        steps = 0
    if lr <= 0:
        lr_b = "lr0"
    else:
        import math

        lr_b = f"lr{int(math.floor(math.log10(lr)))}"
    if steps <= 20:
        st_b = "s20"
    elif steps <= 60:
        st_b = "s60"
    elif steps <= 120:
        st_b = "s120"
    else:
        st_b = "splus"
    hidden = hp.get("HIDDEN", "?")
    l2 = hp.get("L2", "?")
    return f"{lr_b}_{st_b}_h{hidden}_l2{l2}"
