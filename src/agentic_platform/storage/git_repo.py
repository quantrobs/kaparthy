from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


class GitWorkspace:
    """Working-tree Git operations for the measured loop."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", *args],
            cwd=self.path,
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            raise GitError(result.stderr.strip() or result.stdout.strip() or "git failed")
        return result

    def init(self) -> None:
        if not (self.path / ".git").exists():
            self._run("init")
            self._run("config", "user.email", "agent@kaparthy.local")
            self._run("config", "user.name", "Agentic Platform")

    def add_all(self) -> None:
        self._run("add", "-A")

    def commit(self, message: str) -> str:
        self.add_all()
        # Allow empty commits only if needed for baseline
        status = self._run("status", "--porcelain", check=False)
        if not status.stdout.strip():
            # create empty commit only if no HEAD yet
            try:
                return self.head()
            except GitError:
                self._run("commit", "--allow-empty", "-m", message)
                return self.head()
        self._run("commit", "-m", message)
        return self.head()

    def head(self) -> str:
        r = self._run("rev-parse", "HEAD")
        return r.stdout.strip()

    def reset_hard(self, commit: str) -> None:
        self._run("reset", "--hard", commit)

    def checkout(self, commit: str) -> None:
        self._run("checkout", commit)

    def diff_stat(self, a: str, b: str) -> str:
        r = self._run("diff", "--stat", a, b, check=False)
        return r.stdout

    def show_files_changed(self, parent: str, commit: str) -> list[str]:
        r = self._run("diff", "--name-only", parent, commit, check=False)
        return [line for line in r.stdout.splitlines() if line.strip()]

    def is_clean(self) -> bool:
        r = self._run("status", "--porcelain", check=False)
        return not r.stdout.strip()


class BareGitHub:
    """Bare repository serving as the AgentHub commit DAG store."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            subprocess.run(
                ["git", "init", "--bare", str(self.path)],
                check=True,
                capture_output=True,
                text=True,
            )

    def receive_from_workspace(self, workspace: Path, ref: str = "refs/heads/experiments") -> str:
        """Push HEAD of workspace into bare repo under a unique ref; return commit hash."""
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        # Ensure remote exists
        remotes = subprocess.run(
            ["git", "remote"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        if "hub" not in remotes.split():
            subprocess.run(
                ["git", "remote", "add", "hub", str(self.path)],
                cwd=workspace,
                check=True,
                capture_output=True,
                text=True,
            )
        unique_ref = f"{ref}/{head[:12]}"
        subprocess.run(
            ["git", "push", "hub", f"HEAD:{unique_ref}"],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
        )
        return head

    def has_commit(self, commit: str) -> bool:
        r = subprocess.run(
            ["git", "cat-file", "-t", commit],
            cwd=self.path,
            capture_output=True,
            text=True,
        )
        return r.returncode == 0 and r.stdout.strip() == "commit"

    def checkout_to(self, commit: str, dest: Path) -> None:
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        if not (dest / ".git").exists():
            subprocess.run(["git", "init"], cwd=dest, check=True, capture_output=True)
            subprocess.run(
                ["git", "remote", "add", "hub", str(self.path)],
                cwd=dest,
                check=True,
                capture_output=True,
            )
        subprocess.run(
            ["git", "fetch", "hub", commit],
            cwd=dest,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "checkout", commit],
            cwd=dest,
            check=True,
            capture_output=True,
            text=True,
        )
