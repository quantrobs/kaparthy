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
from agentic_platform.loops.fingerprint import fingerprint_workspace
from agentic_platform.loops.pace import can_still_reach, should_keep, wealth_update
from agentic_platform.models.schemas import Trial
from agentic_platform.security.sandbox import SandboxError, run_sandboxed, scan_diff_contents
from agentic_platform.storage.artifacts import ArtifactStore
from agentic_platform.storage.db import Database
from agentic_platform.storage.git_repo import GitWorkspace

_DEMO_TRAIN = '''\
"""Tiny CPU trainer — hostile metric; agents may edit hyperparameters only."""
from __future__ import annotations

import math
import os

# === mutable hyperparameters (agent may edit) ===
LR = 0.05
STEPS = 40
HIDDEN = 8
L2 = 0.0
SEED = 0
# === end mutable ===


def _eval_seed() -> int:
    raw = os.environ.get("AGENTIC_EVAL_SEED")
    if raw is None or str(raw).strip() == "":
        return int(SEED)
    return int(raw)


def main() -> None:
    n = 64
    xs = [(i / n) * 2 - 1 for i in range(n)]
    ys = [math.sin(3 * x) + 0.1 * x for x in xs]

    def rnd(i: int) -> float:
        return math.sin(_eval_seed() * 12.9898 + i * 78.233) * 43758.5453 % 1.0

    w1 = [rnd(i) * 0.5 - 0.25 for i in range(HIDDEN)]
    b1 = [rnd(100 + i) * 0.1 for i in range(HIDDEN)]
    w2 = [rnd(200 + i) * 0.5 - 0.25 for i in range(HIDDEN)]
    b2 = rnd(300) * 0.1

    for _ in range(STEPS):
        g_w1 = [0.0] * HIDDEN
        g_b1 = [0.0] * HIDDEN
        g_w2 = [0.0] * HIDDEN
        g_b2 = 0.0
        for x, y in zip(xs, ys):
            h = [math.tanh(w1[j] * x + b1[j]) for j in range(HIDDEN)]
            pred = sum(w2[j] * h[j] for j in range(HIDDEN)) + b2
            err = pred - y
            g_b2 += 2 * err
            for j in range(HIDDEN):
                g_w2[j] += 2 * err * h[j]
                dh = 2 * err * w2[j] * (1 - h[j] * h[j])
                g_w1[j] += dh * x
                g_b1[j] += dh
        scale = LR / n
        for j in range(HIDDEN):
            w1[j] -= scale * (g_w1[j] + 2 * L2 * w1[j])
            b1[j] -= scale * g_b1[j]
            w2[j] -= scale * (g_w2[j] + 2 * L2 * w2[j])
        b2 -= scale * g_b2

    loss = 0.0
    for x, y in zip(xs, ys):
        h = [math.tanh(w1[j] * x + b1[j]) for j in range(HIDDEN)]
        pred = sum(w2[j] * h[j] for j in range(HIDDEN)) + b2
        err = pred - y
        loss += err * err
    val_loss = loss / n + L2 * (sum(w * w for w in w1) + sum(w * w for w in w2))
    print(f"val_loss={val_loss:.6f}")


if __name__ == "__main__":
    main()
'''

_DEMO_PREPARE = "# protected evaluation surface — agents must never modify this file\nprint('ready')\n"


class LoopService:
    """Measured ratchet loop: inspect → propose → commit → evaluate → keep/revert → log."""

    def __init__(
        self,
        db: Database,
        artifacts: ArtifactStore,
        control: ControlService,
        audit_hook: Callable[[str | None, str, dict[str, Any]], None] | None = None,
        dag: Any | None = None,
    ) -> None:
        self.db = db
        self.artifacts = artifacts
        self.control = control
        self.audit_hook = audit_hook or (lambda *a, **k: None)
        self.dag = dag

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

        try:
            head = git.head()
        except Exception:
            self._seed_workspace(workspace, ctl)
            head = git.commit("baseline")

        program_path = workspace / "program.md"
        if not program_path.exists():
            program_path.write_text(ControlService.render_program(ctl), encoding="utf-8")
            try:
                head = git.commit("add program.md")
            except Exception:
                head = git.head()

        best_metric: float | None = None
        try:
            best_metric = self._run_and_parse_metric(workspace, ctl)
        except Exception:
            best_metric = None

        loop_id = new_id("loop_")
        payload = {
            "id": loop_id,
            "control_document_id": control_document_id,
            "workspace_path": str(workspace.resolve()),
            "best_commit": head,
            "best_metric": best_metric,
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
                best_metric,
                "running",
                self.db.dumps(payload),
                payload["created_at"],
            ),
        )
        self.audit_hook(None, "loop.started", payload)
        return payload

    def _seed_workspace(self, workspace: Path, ctl: dict[str, Any]) -> None:
        workspace.mkdir(parents=True, exist_ok=True)
        if not (workspace / "train.py").exists():
            (workspace / "train.py").write_text(_DEMO_TRAIN, encoding="utf-8")
        if not (workspace / "prepare.py").exists():
            (workspace / "prepare.py").write_text(_DEMO_PREPARE, encoding="utf-8")
        program = ctl.get("program_md") or ControlService.render_program(ctl)
        (workspace / "program.md").write_text(program, encoding="utf-8")

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
        reproducible = False
        if loop.get("best_commit") is not None and loop.get("best_metric") is not None:
            try:
                repro = self.reproduce_metric(loop_id, loop["best_commit"])
                reproducible = bool(repro.get("matches_recorded_best"))
            except Exception:
                reproducible = False
        return {
            "loop_id": loop_id,
            "best_commit": loop.get("best_commit"),
            "best_metric": loop.get("best_metric"),
            "kept_count": len(kept),
            "reproducible_from_commit": reproducible,
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
        parent_commit: str | None = None,
    ) -> dict[str, Any]:
        loop = self.get(loop_id)
        if not loop:
            raise ValueError(f"unknown loop: {loop_id}")
        ctl = self.control.get(loop["control_document_id"])
        if not ctl:
            raise ValueError("control document missing")

        workspace = Path(loop["workspace_path"])
        git = GitWorkspace(workspace)
        parent = parent_commit or loop["best_commit"]
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
            # C1: override can never keep
            if metric_override is not None:
                InvariantGuard.reject_metric_override_for_keep(metric_override)

            trial["status"] = "running"
            if patch_fn:
                patch_fn(workspace)
            if file_edits:
                for rel, content in file_edits.items():
                    target = workspace / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8")

            git.add_all()
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=workspace,
                capture_output=True,
                text=True,
                check=True,
            )
            changed: list[str] = []
            for line in status.stdout.splitlines():
                if len(line) >= 4:
                    changed.append(line[3:].strip().strip('"'))

            InvariantGuard.reject_protected_edits(changed, ctl.get("protected_paths") or [])
            InvariantGuard.reject_outside_mutable(changed, ctl.get("mutable_paths"))
            InvariantGuard.reject_holdout_authorship(changed)

            total_bytes = 0
            for rel in changed:
                p = workspace / rel
                if p.is_file():
                    total_bytes += p.stat().st_size
            InvariantGuard.reject_oversized_diff(changed, total_bytes)
            scan_diff_contents(workspace, changed)

            fp = fingerprint_workspace(workspace)
            if fp:
                trial["fingerprint"] = fp
                hit = self.db.fetchone(
                    "SELECT trial_id FROM trial_fingerprints "
                    "WHERE control_document_id = ? AND fingerprint = ?",
                    (loop["control_document_id"], fp),
                )
                if hit:
                    raise InvariantError(2, f"duplicate_of:{hit['trial_id']}")

            if simulate_crash:
                raise RuntimeError("simulated crash mid-training")

            commit_hash = git.commit(f"trial: {hypothesis[:72]}")
            trial["commit_hash"] = commit_hash
            trial["diff_summary"] = git.diff_stat(parent, commit_hash)[:2000]

            t0 = time.time()
            kg = ctl.get("keep_gate") or {}
            mode = kg.get("mode") or "single_shot"
            if mode == "paired_pace":
                incumbent = loop.get("best_commit") or parent
                better, cert, metric_value = self._evaluate_paired(
                    workspace, git, ctl, incumbent, commit_hash
                )
                InvariantGuard.require_sealed_keep(cert, mode)
                trial["keep_certificate"] = cert
                trial["metric_name"] = ctl["metric"]["name"]
                trial["metric_value"] = metric_value
                try:
                    self._record_evaluation(trial, cert, better)
                except Exception:
                    pass
            else:
                metric_value = self._run_and_parse_metric(workspace, ctl)
                trial["metric_name"] = ctl["metric"]["name"]
                trial["metric_value"] = metric_value
                better = InvariantGuard.require_metric_improvement(
                    direction=ctl["metric"]["direction"],
                    comparison=ctl["comparison"]["function"],
                    baseline=loop.get("best_metric"),
                    candidate=metric_value,
                    epsilon=ctl["comparison"].get("epsilon"),
                )
            wall = time.time() - t0
            trial["wall_time_seconds"] = wall

            if better:
                trial["status"] = "kept"
                loop["best_commit"] = commit_hash
                loop["best_metric"] = metric_value
            else:
                trial["status"] = "reverted"

            self._push_evidence(workspace, trial, agent_id, hypothesis)

            if trial["status"] == "reverted":
                git.reset_hard(parent)
                InvariantGuard.require_runnable(workspace)

            if fp:
                self._store_fingerprint(loop_id, loop["control_document_id"], fp, trial_id)

        except (InvariantError, SandboxError) as e:
            trial["status"] = "rejected"
            trial["error"] = str(e)
            try:
                git.reset_hard(parent)
            except Exception:
                pass
        except Exception as e:
            trial["status"] = "crash"
            trial["error"] = str(e)
            try:
                git.reset_hard(parent)
            except Exception:
                pass
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

    def _run_and_parse_metric(
        self,
        workspace: Path,
        ctl: dict[str, Any],
        extra_env: dict[str, str] | None = None,
    ) -> float:
        cmd = ctl["run_command"]
        timeout = float(ctl.get("time_budget_seconds") or 60)
        result = run_sandboxed(cmd, workspace, timeout=timeout, strict_cmd=True, extra_env=extra_env)
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        pattern = ctl["metric"]["parse_regex"]
        # Use last match so agents cannot prepend a fake val_loss= print (Phase 5)
        matches = list(re.finditer(pattern, output))
        if not matches:
            raise RuntimeError(
                f"metric not found (rc={result.returncode}) regex={pattern!r}: {output[:500]}"
            )
        return float(matches[-1].group(1))

    def _evaluate_paired(
        self,
        workspace: Path,
        git: GitWorkspace,
        ctl: dict[str, Any],
        incumbent_hash: str,
        candidate_hash: str,
    ) -> tuple[bool, dict[str, Any], float | None]:
        kg = ctl.get("keep_gate") or {}
        seeds = [int(s) for s in (kg.get("seeds") or [])]
        n_min = int(kg.get("n_min") or 3)
        n_max = int(kg.get("n_max") or max(n_min, len(seeds) or n_min))
        alpha = float(kg.get("alpha") or 0.05)
        lam = float(kg.get("lambda") or 0.4)
        seed_env = str(kg.get("seed_env") or "AGENTIC_EVAL_SEED")
        if not seeds:
            seeds = list(range(n_min))
        seeds = seeds[:n_max]

        wealth = 1.0
        wins = 0
        losses = 0
        inc_vals: list[float] = []
        cand_vals: list[float] = []
        early = False
        direction = ctl["metric"]["direction"]
        comparison = ctl["comparison"]["function"]
        epsilon = ctl["comparison"].get("epsilon")

        for i, seed in enumerate(seeds):
            env = {seed_env: str(seed)}
            git.reset_hard(incumbent_hash)
            inc = self._run_and_parse_metric(workspace, ctl, extra_env=env)
            git.reset_hard(candidate_hash)
            cand = self._run_and_parse_metric(workspace, ctl, extra_env=env)
            inc_vals.append(inc)
            cand_vals.append(cand)
            won = InvariantGuard.require_metric_improvement(
                direction=direction,
                comparison=comparison,
                baseline=inc,
                candidate=cand,
                epsilon=epsilon,
            )
            wealth = wealth_update(wealth, won, lam)
            if won:
                wins += 1
            else:
                losses += 1
            remaining = len(seeds) - (i + 1)
            n_pairs = wins + losses
            if should_keep(wealth, n_pairs, n_min, alpha):
                break
            if n_pairs >= n_min and not can_still_reach(wealth, remaining, lam, alpha):
                early = True
                break

        n_pairs = wins + losses
        mean_inc = sum(inc_vals) / len(inc_vals) if inc_vals else None
        mean_cand = sum(cand_vals) / len(cand_vals) if cand_vals else None
        cert = {
            "mode": "paired_pace",
            "n_pairs": n_pairs,
            "wins": wins,
            "losses": losses,
            "e_value": wealth,
            "alpha": alpha,
            "mean_incumbent": mean_inc,
            "mean_candidate": mean_cand,
            "early_stopped": early,
        }
        keep = should_keep(wealth, n_pairs, n_min, alpha)
        return keep, cert, mean_cand

    def _store_fingerprint(
        self, loop_id: str, control_document_id: str, fingerprint: str, trial_id: str
    ) -> None:
        self.db.execute(
            "INSERT INTO trial_fingerprints "
            "(loop_id, control_document_id, fingerprint, trial_id, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (loop_id, control_document_id, fingerprint, trial_id, utc_now_iso()),
        )

    def _push_evidence(
        self,
        workspace: Path,
        trial: dict[str, Any],
        agent_id: str,
        hypothesis: str,
    ) -> None:
        if not self.dag or not trial.get("commit_hash"):
            return
        status = trial["status"]
        dag_status = "kept" if status == "kept" else "reverted" if status == "reverted" else "evidence"
        try:
            self.dag.push(
                workspace,
                agent_id=agent_id,
                hypothesis=hypothesis,
                metric_name=trial.get("metric_name"),
                metric_value=trial.get("metric_value"),
                status=dag_status,
            )
        except Exception:
            pass

    def _record_evaluation(
        self, trial: dict[str, Any], cert: dict[str, Any], better: bool
    ) -> None:
        from agentic_platform.eval.service import EvalService

        # Persist a sealed EvaluationResult without seeds. LoopService may
        # not own EvalService; write through the same DB table if present.
        payload = {
            "id": new_id("eval_"),
            "decision": "pass" if better else "fail",
            "target": trial.get("commit_hash") or trial["id"],
            "rubric": "paired_pace sealed keep-gate",
            "confidence": 1.0,
            "created_at": utc_now_iso(),
            "e_value": cert.get("e_value"),
            "n_instances": cert.get("n_pairs"),
            "sealed": True,
            "pair_summary": {
                "wins": cert.get("wins"),
                "losses": cert.get("losses"),
                "mean_incumbent": cert.get("mean_incumbent"),
                "mean_candidate": cert.get("mean_candidate"),
                "early_stopped": cert.get("early_stopped"),
            },
            "notes": "sealed; seeds omitted",
        }
        EvalService(self.db).create(payload)

    def recover(self, loop_id: str) -> dict[str, Any]:
        """Phase 5 recovery: hard-reset workspace to last kept best; re-mark loop running."""
        loop = self.get(loop_id)
        if not loop:
            raise ValueError(f"unknown loop: {loop_id}")
        workspace = Path(loop["workspace_path"])
        git = GitWorkspace(workspace)
        best = loop.get("best_commit")
        if not best:
            raise ValueError("loop has no best_commit to recover to")
        git.reset_hard(best)
        InvariantGuard.require_runnable(workspace)
        loop["status"] = "running"
        # drop transient dirty state
        self.db.execute(
            "UPDATE loops SET status = ?, payload = ? WHERE id = ?",
            ("running", self.db.dumps(loop), loop_id),
        )
        self.audit_hook(None, "loop.recovered", {"loop_id": loop_id, "best_commit": best})
        # verify metric still parses
        ctl = self.control.get(loop["control_document_id"])
        metric = None
        if ctl:
            try:
                metric = self._run_and_parse_metric(workspace, ctl)
            except Exception as e:
                return {
                    "loop_id": loop_id,
                    "recovered": True,
                    "best_commit": best,
                    "metric_ok": False,
                    "error": str(e),
                }
        return {
            "loop_id": loop_id,
            "recovered": True,
            "best_commit": best,
            "metric_ok": True,
            "metric_value": metric,
            "matches_best": (
                loop.get("best_metric") is None
                or metric is None
                or abs(float(metric) - float(loop["best_metric"])) < 1e-5
            ),
        }

    def reproduce_metric(self, loop_id: str, commit_hash: str | None = None) -> dict[str, Any]:
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
        recorded = loop.get("best_metric")
        matches = recorded is None or abs(metric - float(recorded)) < 1e-5
        return {
            "commit_hash": target,
            "metric_name": ctl["metric"]["name"],
            "metric_value": metric,
            "matches_recorded_best": matches,
        }
