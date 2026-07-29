from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from agentic_platform.control.service import ControlService
from agentic_platform.core.ids import new_id
from agentic_platform.core.timeutil import utc_now_iso
from agentic_platform.core.validation import assert_valid
from agentic_platform.invariants.checks import InvariantError, InvariantGuard
from agentic_platform.models.schemas import Trial
from agentic_platform.storage.artifacts import ArtifactStore
from agentic_platform.storage.db import Database
from agentic_platform.storage.git_repo import GitWorkspace


class LoopService:
    """Measured ratchet loop: inspect → propose → commit → evaluate → keep/revert → log."""

    def __init__(
        self,
        db: Database,
        artifacts: ArtifactStore,
        control: ControlService,
        audit_hook: Callable[[str | None, str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.db = db
        self.artifacts = artifacts
        self.control = control
        self.audit_hook = audit_hook or (lambda *a, **k: None)

    def start(
        self,
        control_document_id: str,
        workspace_path: str | Path,
        agent_id: str = "system",
    ) -> dict[str, Any]:
        ctl = self.control.get(control_document_id)
        if not ctl:
            raise ValueError(f"unknown control document: {control_document_id}")

        workspace = Path(workspace_path)
        git = GitWorkspace(workspace)
        git.init()

        # Ensure baseline commit exists
        try:
            head = git.head()
        except Exception:
            # seed baseline files if empty
            if not any(workspace.iterdir()):
                (workspace / "train.py").write_text(
                    "metric = 1.0\nprint(f'val_loss={metric}')\n",
                    encoding="utf-8",
                )
                (workspace / "prepare.py").write_text(
                    "# protected evaluation surface\nprint('ready')\n",
                    encoding="utf-8",
                )
                (workspace / "program.md").write_text(
                    ctl.get("program_md") or ctl["objective"],
                    encoding="utf-8",
                )
            head = git.commit("baseline")

        loop_id = new_id("loop_")
        payload = {
            "id": loop_id,
            "control_document_id": control_document_id,
            "workspace_path": str(workspace.resolve()),
            "best_commit": head,
            "best_metric": None,
            "status": "running",
            "agent_id": agent_id,
            "created_at": utc_now_iso(),
        }
        self.db.execute(
            "INSERT INTO loops (id, control_document_id, workspace_path, best_commit, best_metric, status, payload, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                loop_id,
                control_document_id,
                str(workspace.resolve()),
                head,
                None,
                "running",
                self.db.dumps(payload),
                payload["created_at"],
            ),
        )
        self.audit_hook(None, "loop.started", payload)
        return payload

    def get(self, loop_id: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT payload FROM loops WHERE id = ?", (loop_id,))
        return self.db.loads(row["payload"]) if row else None

    def list_trials(self, loop_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT payload FROM trials WHERE loop_id = ? ORDER BY created_at",
            (loop_id,),
        )
        return [self.db.loads(r["payload"]) for r in rows]

    def best(self, loop_id: str) -> dict[str, Any]:
        loop = self.get(loop_id)
        if not loop:
            raise ValueError(f"unknown loop: {loop_id}")
        kept = [t for t in self.list_trials(loop_id) if t["status"] == "kept"]
        return {
            "loop_id": loop_id,
            "best_commit": loop.get("best_commit"),
            "best_metric": loop.get("best_metric"),
            "kept_count": len(kept),
            "reproducible_from_commit": True,
        }

    def propose_trial(
        self,
        loop_id: str,
        agent_id: str,
        hypothesis: str,
        patch_fn: Callable[[Path], None] | None = None,
        file_edits: dict[str, str] | None = None,
        simulate_crash: bool = False,
        metric_override: float | None = None,
    ) -> dict[str, Any]:
        loop = self.get(loop_id)
        if not loop:
            raise ValueError(f"unknown loop: {loop_id}")
        ctl = self.control.get(loop["control_document_id"])
        if not ctl:
            raise ValueError("control document missing")

        workspace = Path(loop["workspace_path"])
        git = GitWorkspace(workspace)
        parent = loop["best_commit"]
        git.reset_hard(parent)
        InvariantGuard.require_runnable(workspace)

        trial_id = new_id("trial_")
        created = utc_now_iso()
        trial: dict[str, Any] = {
            "id": trial_id,
            "control_document_id": loop["control_document_id"],
            "parent_commit": parent,
            "agent_id": agent_id,
            "hypothesis": hypothesis,
            "status": "proposed",
            "created_at": created,
        }

        try:
            trial["status"] = "running"
            # Apply edits
            if patch_fn:
                patch_fn(workspace)
            if file_edits:
                for rel, content in file_edits.items():
                    target = workspace / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8")

            # Detect changed files before commit for protected-path check
            git.add_all()
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=workspace,
                capture_output=True,
                text=True,
                check=True,
            )
            changed = []
            for line in status.stdout.splitlines():
                if len(line) >= 4:
                    changed.append(line[3:].strip().strip('"'))

            InvariantGuard.reject_protected_edits(changed, ctl.get("protected_paths") or [])

            if simulate_crash:
                raise RuntimeError("simulated crash mid-training")

            commit_hash = git.commit(f"trial: {hypothesis[:72]}")
            trial["commit_hash"] = commit_hash
            trial["diff_summary"] = git.diff_stat(parent, commit_hash)[:2000]

            # Evaluate
            t0 = time.time()
            if metric_override is not None:
                metric_value = float(metric_override)
            else:
                metric_value = self._run_and_parse_metric(workspace, ctl)
            wall = time.time() - t0
            trial["metric_name"] = ctl["metric"]["name"]
            trial["metric_value"] = metric_value
            trial["wall_time_seconds"] = wall

            better = InvariantGuard.require_metric_improvement(
                direction=ctl["metric"]["direction"],
                comparison=ctl["comparison"]["function"],
                baseline=loop.get("best_metric"),
                candidate=metric_value,
                epsilon=ctl["comparison"].get("epsilon"),
            )

            if better:
                trial["status"] = "kept"
                loop["best_commit"] = commit_hash
                loop["best_metric"] = metric_value
            else:
                trial["status"] = "reverted"
                git.reset_hard(parent)
                InvariantGuard.require_runnable(workspace)

        except InvariantError as e:
            trial["status"] = "rejected"
            trial["error"] = str(e)
            git.reset_hard(parent)
        except Exception as e:
            trial["status"] = "crash"
            trial["error"] = str(e)
            git.reset_hard(parent)
            InvariantGuard.require_runnable(workspace)

        trial["finished_at"] = utc_now_iso()
        ledger_uri = self.artifacts.append_ledger(
            loop_id,
            {"trial": trial, "loop_best": loop.get("best_commit")},
        )
        trial["ledger_entry_uri"] = ledger_uri

        Trial.model_validate(trial)
        assert_valid("Trial", {k: v for k, v in trial.items() if v is not None})

        self.db.execute(
            "INSERT INTO trials (id, loop_id, control_document_id, payload, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                trial_id,
                loop_id,
                loop["control_document_id"],
                self.db.dumps(trial),
                trial["status"],
                created,
            ),
        )
        self.db.execute(
            "UPDATE loops SET best_commit = ?, best_metric = ?, payload = ? WHERE id = ?",
            (
                loop.get("best_commit"),
                loop.get("best_metric"),
                self.db.dumps(loop),
                loop_id,
            ),
        )
        self.audit_hook(None, "loop.trial", trial)
        return trial

    def _run_and_parse_metric(self, workspace: Path, ctl: dict[str, Any]) -> float:
        cmd = ctl["run_command"]
        # Bound wall time softly via timeout
        timeout = float(ctl.get("time_budget_seconds") or 60)
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        pattern = ctl["metric"]["parse_regex"]
        m = re.search(pattern, output)
        if not m:
            raise RuntimeError(f"metric not found with regex {pattern!r} in output: {output[:500]}")
        return float(m.group(1))

    def reproduce_metric(self, loop_id: str, commit_hash: str | None = None) -> dict[str, Any]:
        """Acceptance: best metric reproducible from commit hash alone."""
        loop = self.get(loop_id)
        if not loop:
            raise ValueError(f"unknown loop: {loop_id}")
        ctl = self.control.get(loop["control_document_id"])
        if not ctl:
            raise ValueError("control missing")
        workspace = Path(loop["workspace_path"])
        git = GitWorkspace(workspace)
        target = commit_hash or loop["best_commit"]
        git.reset_hard(target)
        metric = self._run_and_parse_metric(workspace, ctl)
        return {
            "commit_hash": target,
            "metric_name": ctl["metric"]["name"],
            "metric_value": metric,
            "matches_recorded_best": (
                loop.get("best_metric") is None or abs(metric - float(loop["best_metric"])) < 1e-9
            ),
        }
