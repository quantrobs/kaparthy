from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from agentic_platform.security.secrets import find_secrets, scan_paths


class SandboxError(Exception):
    """Raised when sandbox policy blocks an action."""


# Shell metacharacters / chaining that expand blast radius of run_command
_DANGEROUS_SHELL = re.compile(
    r"(?:\$\(|`|\|\||&&|;|\n|\r|>>(?!>)|(?<![>|])\|(?!\|)|(?<!\&)\&(?!\&)|>(?!>)|<(?!<))"
)

# Allow only simple python invocations by default for demo/production pilot
_DEFAULT_CMD_ALLOW = re.compile(
    r"^python(?:3)?(?:\s+-u)?\s+[\w./\\-]+\.py(?:\s+.*)?$",
    re.IGNORECASE,
)


def scan_for_secrets(file_contents: dict[str, str]) -> None:
    hits = scan_paths(file_contents.items())
    if hits:
        raise SandboxError(f"secret patterns detected: {', '.join(hits)}")


def validate_run_command(cmd: str, *, strict: bool = True) -> None:
    """Block obvious shell injection / multi-command chains in run_command."""
    c = cmd.strip()
    if not c:
        raise SandboxError("empty run_command")
    if len(c) > 500:
        raise SandboxError("run_command too long")
    if _DANGEROUS_SHELL.search(c):
        raise SandboxError("run_command contains disallowed shell metacharacters")
    # Block absolute paths outside cwd-style invocation
    if re.search(r"(?i)\b(curl|wget|nc|ncat|ssh|scp|powershell|cmd\.exe|bash\s+-c)\b", c):
        raise SandboxError("run_command invokes disallowed binary")
    if strict and not _DEFAULT_CMD_ALLOW.match(c):
        # Allow env override for advanced research harnesses
        if os.environ.get("AGENTIC_ALLOW_ARBITRARY_RUN_CMD") != "1":
            raise SandboxError(
                "run_command not on allowlist (python script only); "
                "set AGENTIC_ALLOW_ARBITRARY_RUN_CMD=1 to override"
            )


def scrubbed_env() -> dict[str, str]:
    """Minimal env for child processes — strip secrets from parent environment."""
    keep_prefixes = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG", "LC_")
    keep_exact = {
        "PATH",
        "SystemRoot",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "TMPDIR",
        "HOME",
        "USERPROFILE",
        "USERNAME",
        "USER",
        "LANG",
        "PYTHONPATH",
        "VIRTUAL_ENV",
        "PATHEXT",
        "COMSPEC",
        "NUMBER_OF_PROCESSORS",
    }
    drop_substrings = (
        "KEY",
        "SECRET",
        "TOKEN",
        "PASSWORD",
        "CREDENTIAL",
        "AWS_",
        "AZURE_",
        "OPENAI",
        "ANTHROPIC",
        "GITHUB",
    )
    out: dict[str, str] = {}
    for k, v in os.environ.items():
        ku = k.upper()
        if any(s in ku for s in drop_substrings):
            continue
        if k in keep_exact or any(ku.startswith(p) for p in keep_prefixes):
            out[k] = v
    # Ensure python can run
    if "PATH" not in out and "Path" in os.environ:
        out["PATH"] = os.environ["Path"]
    out["AGENTIC_SANDBOX"] = "1"
    out["PYTHONDONTWRITEBYTECODE"] = "1"
    return out


def run_sandboxed(
    cmd: str,
    cwd: Path,
    timeout: float,
    *,
    strict_cmd: bool = True,
) -> subprocess.CompletedProcess[str]:
    validate_run_command(cmd, strict=strict_cmd)
    env = scrubbed_env()
    try:
        return subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as e:
        raise SandboxError(f"run_command timed out after {timeout}s") from e


def scan_diff_contents(workspace: Path, changed_files: list[str]) -> None:
    contents: dict[str, str] = {}
    for rel in changed_files:
        p = workspace / rel
        if not p.is_file():
            continue
        try:
            if p.stat().st_size > 1_000_000:
                raise SandboxError(f"file too large to scan: {rel}")
            text = p.read_text(encoding="utf-8", errors="replace")
        except UnicodeError:
            raise SandboxError(f"binary or unreadable file not allowed: {rel}")
        contents[rel] = text
        # also flag secrets in content via find_secrets for clearer errors
        hits = find_secrets(text)
        if hits:
            raise SandboxError(f"secret patterns in {rel}: {', '.join(hits)}")
    scan_for_secrets(contents)
