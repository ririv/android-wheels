"""Resolve GitHub refs and validate an explicitly selected source project."""

import base64
import json
import subprocess
import tomllib
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from scripts.build.normalize_repo_input import normalize_repo_input
from scripts.pipeline.model import Source
from scripts.recipes.model import Backend


def github(endpoint: str) -> dict:
    return json.loads(subprocess.check_output(["gh", "api", endpoint], text=True))


def backend_from_text(text: str) -> Backend:
    data = tomllib.loads(text)
    return Backend(data["build-system"]["build-backend"])


def backend_at(project: Path) -> Backend:
    if not (project / "pyproject.toml").is_file():
        raise FileNotFoundError(f"项目目录缺少 pyproject.toml：{project}")
    return backend_from_text((project / "pyproject.toml").read_text(encoding="utf-8"))


def resolve_source(repository: str, ref: str, directory: str) -> Source:
    repository = normalize_repo_input(repository)
    if not directory:
        raise ValueError("必须显式填写项目目录，根目录使用 .")
    project = PurePosixPath(directory)
    if project.is_absolute() or ".." in project.parts or "\\" in directory:
        raise ValueError("项目目录必须是仓库内的相对路径")
    if not ref:
        ref = github(f"repos/{repository}")["default_branch"]
    sha = github(f"repos/{repository}/commits/{quote(ref, safe='')}")["sha"]
    path = (project / "pyproject.toml").as_posix()
    contents = github(f"repos/{repository}/contents/{quote(path)}?ref={sha}")
    backend = backend_from_text(base64.b64decode(contents["content"]).decode("utf-8"))
    return Source(repository, ref, sha, project.as_posix(), backend)


def verify_checkout(source: Source, checkout: Path) -> None:
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
    ).strip()
    if sha != source.sha:
        raise ValueError(f"源码提交不匹配：{sha} != {source.sha}")
    actual = backend_at(checkout / source.directory)
    if actual != source.backend:
        raise ValueError(f"源码后端不匹配：{actual} != {source.backend}")
