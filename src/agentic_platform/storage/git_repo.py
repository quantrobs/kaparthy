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
        status = self._run("status", "--porcelain", check=False)
        if not status.stdout.strip():
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

    def is_clean(self) -> bool:
        r = self._run("status", "--porcelain", check=False)
        return not r.stdout.strip()

    def parents_of(self, commit_hash: str) -> list[str]:
        r = self._run("rev-parse", f"{commit_hash}^@", check=False)
        if r.returncode != 0:
            return []
        return [line.strip() for line in r.stdout.splitlines() if line.strip()]


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
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
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
        else:
            subprocess.run(
                ["git", "remote", "set-url", "hub", str(self.path)],
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

    def parents_of(self, commit_hash: str) -> list[str]:
        r = subprocess.run(
            ["git", "rev-parse", f"{commit_hash}^@"],
            cwd=self.path,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            return []
        return [line.strip() for line in r.stdout.splitlines() if line.strip()]

    def resolve_hash(self, prefix: str) -> str | None:
        if self.has_commit(prefix):
            return prefix
        r = subprocess.run(
            ["git", "rev-parse", "--verify", prefix],
            cwd=self.path,
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            return r.stdout.strip()
        return None

    def checkout_to(self, commit: str, dest: Path) -> None:
        """Materialize commit into dest as a full working repo (Git objects from bare hub)."""
        import shutil

        dest = Path(dest)
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        subprocess.run(
            ["git", "init"],
            cwd=dest,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "agent@kaparthy.local"],
            cwd=dest,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Agentic Platform"],
            cwd=dest,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "remote", "add", "hub", str(self.path)],
            cwd=dest,
            check=True,
            capture_output=True,
            text=True,
        )
        # Pull all refs/objects from bare hub (custom experiment refs included)
        fetch = subprocess.run(
            ["git", "fetch", "hub", "+refs/*:refs/remotes/hub/*"],
            cwd=dest,
            capture_output=True,
            text=True,
        )
        if fetch.returncode != 0:
            # Fallback: mirror-style fetch
            subprocess.run(
                ["git", "fetch", "hub", "+refs/*:refs/*"],
                cwd=dest,
                check=True,
                capture_output=True,
                text=True,
            )
        subprocess.run(
            ["git", "checkout", "-f", commit],
            cwd=dest,
            check=True,
            capture_output=True,
            text=True,
        )
