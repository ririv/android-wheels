"""Publish a fully verified build in one Git commit, preserving concurrent updates."""

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Published:
    revision: str


@dataclass(frozen=True)
class Unchanged:
    revision: str


PublishResult = Published | Unchanged


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def publish(root: Path, wheels: dict[str, Path], run_url: str) -> PublishResult:
    if not wheels:
        raise ValueError("禁止发布空产物集合")
    for attempt in range(3):
        git(root, "fetch", "--depth=1", "origin", "wheels")
        base = git(root, "rev-parse", "FETCH_HEAD")
        with tempfile.TemporaryDirectory(prefix="wheel-publish-") as temporary:
            checkout = Path(temporary) / "checkout"
            git(root, "worktree", "add", "--detach", str(checkout), base)
            try:
                for relative, source in wheels.items():
                    destination = checkout / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                git(checkout, "add", "--", *sorted(wheels))
                if not git(checkout, "diff", "--cached", "--name-only"):
                    return Unchanged(base)
                git(
                    checkout,
                    "-c",
                    "user.name=github-actions[bot]",
                    "-c",
                    "user.email=github-actions[bot]@users.noreply.github.com",
                    "commit",
                    "-m",
                    f"发布已校验 wheels：{run_url}",
                )
                revision = git(checkout, "rev-parse", "HEAD")
                pushed = subprocess.run(
                    ["git", "push", "origin", "HEAD:refs/heads/wheels"],
                    cwd=checkout,
                    capture_output=True,
                    text=True,
                )
                if pushed.returncode == 0:
                    print(pushed.stdout, pushed.stderr)
                    return Published(revision)
                remote = git(root, "ls-remote", "origin", "refs/heads/wheels").split()[
                    0
                ]
                if remote == base:
                    raise RuntimeError(f"发布失败：{pushed.stderr}")
                print(f"wheels 分支已更新，重新组合提交（{attempt + 1}/3）")
            finally:
                git(root, "worktree", "remove", "--force", str(checkout))
    raise RuntimeError("wheels 分支持续更新，三次发布均被拒绝")
