"""Resolve GitHub refs and validate an explicitly selected source project."""

import base64
import json
import shutil
import subprocess
import tempfile
import tomllib
import urllib.request
from collections.abc import Callable
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from scripts.build.normalize_repo_input import normalize_repo_input
from scripts.pipeline.model import GitSource, SdistSource, Source
from scripts.pipeline.sdists import download, extract
from scripts.pipeline.wheel import normalized
from scripts.recipes.model import Backend, Location, PyPILocation


def github(endpoint: str) -> dict:
    return json.loads(subprocess.check_output(["gh", "api", endpoint], text=True))


def backend_from_text(text: str) -> Backend:
    data = tomllib.loads(text)
    return Backend(data["build-system"]["build-backend"])


def backend_at(project: Path) -> Backend:
    if not (project / "pyproject.toml").is_file():
        raise FileNotFoundError(f"项目目录缺少 pyproject.toml：{project}")
    return backend_from_text((project / "pyproject.toml").read_text(encoding="utf-8"))


def resolve_source(location: Location, directory: str) -> Source:
    if isinstance(location, PyPILocation):
        return resolve_sdist(location, directory, backend_at)
    repository = normalize_repo_input(location.repository)
    ref = location.ref
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
    return GitSource(repository, ref, sha, project.as_posix(), backend)


def verify_checkout(source: GitSource, checkout: Path) -> None:
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
    ).strip()
    if sha != source.sha:
        raise ValueError(f"源码提交不匹配：{sha} != {source.sha}")
    actual = backend_at(checkout / source.directory)
    if actual != source.backend:
        raise ValueError(f"源码后端不匹配：{actual} != {source.backend}")


def legacy_backend_at(project: Path) -> Backend:
    if not (project / "setup.py").is_file():
        raise FileNotFoundError("显式 legacy setuptools 项目必须有 setup.py")
    metadata = project / "pyproject.toml"
    if metadata.is_file():
        build = tomllib.loads(metadata.read_text(encoding="utf-8")).get(
            "build-system", {}
        )
        if "build-backend" in build or "backend-path" in build:
            raise ValueError("显式 legacy 模式不能覆盖项目已声明的后端")
    return Backend.SETUPTOOLS_LEGACY


def resolve_legacy_sdist(location: PyPILocation, directory: str) -> SdistSource:
    return resolve_sdist(location, directory, legacy_backend_at)


def verify_sdist_project(source: SdistSource, root: Path) -> None:
    project = root / source.directory
    reader = (
        legacy_backend_at if source.backend == Backend.SETUPTOOLS_LEGACY else backend_at
    )
    if reader(project) != source.backend:
        raise ValueError("PyPI 源码后端与构建计划不一致")
    metadata = BytesParser().parsebytes((root / "PKG-INFO").read_bytes())
    if (
        normalized(metadata["Name"]) != normalized(source.package)
        or metadata["Version"] != source.version
    ):
        raise ValueError("sdist PKG-INFO 与所选包或版本不一致")


def resolve_sdist(
    location: PyPILocation, directory: str, reader: Callable[[Path], Backend]
) -> SdistSource:
    path = PurePosixPath(directory)
    if not directory or path.is_absolute() or ".." in path.parts or "\\" in directory:
        raise ValueError("项目目录必须明确位于源码根目录内")
    url = f"https://pypi.org/pypi/{quote(location.package, safe='')}/{quote(location.version, safe='')}/json"
    with urllib.request.urlopen(url, timeout=30) as response:
        data = json.load(response)
    releases = [
        row
        for row in data["urls"]
        if row["packagetype"] == "sdist" and not row["yanked"]
    ]
    if len(releases) != 1:
        raise ValueError("指定 PyPI 版本必须包含唯一、未撤回的官方 sdist")
    release = releases[0]
    filename = release["filename"]
    if Path(filename).name != filename:
        raise ValueError("无效的 sdist 文件名")
    with tempfile.TemporaryDirectory(prefix="resolve-sdist-") as temporary:
        archive = download(
            release["url"], release["digests"]["sha256"], Path(temporary) / filename
        )
        root = extract(archive, Path(temporary) / "source")
        source = SdistSource(
            location.package,
            location.version,
            release["url"],
            release["digests"]["sha256"],
            filename,
            path.as_posix(),
            reader(root / path),
        )
        verify_sdist_project(source, root)
    return source


def prepare_sdist(source: SdistSource, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"源码目录已存在：{destination}")
    with tempfile.TemporaryDirectory(prefix="prepare-sdist-") as temporary:
        archive = download(source.url, source.sha256, Path(temporary) / source.filename)
        root = extract(archive, Path(temporary) / "source")
        verify_sdist_project(source, root)
        shutil.copytree(root, destination)
