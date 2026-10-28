"""Match evidenced upstream incompatibilities to immutable source identities."""

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from scripts.build.android_python import PythonVersion
from scripts.recipes.load import require_keys


@dataclass(frozen=True)
class GitCommit:
    sha: str
    kind: Literal["git"] = field(init=False, default="git")


@dataclass(frozen=True)
class SdistArchive:
    sha256: str
    kind: Literal["pypi-sdist"] = field(init=False, default="pypi-sdist")


SourceIdentity = GitCommit | SdistArchive


@dataclass(frozen=True)
class UpstreamUnsupported:
    library: str
    python: PythonVersion
    source: SourceIdentity
    detail: str
    evidence: str
    reason: Literal["upstream-incompatibility"] = field(
        init=False, default="upstream-incompatibility"
    )


def source_identity(data: dict) -> SourceIdentity:
    match data["kind"]:
        case "git":
            require_keys(data, {"kind", "sha"}, "兼容性源码")
            if not re.fullmatch(r"[a-f0-9]{40}", data["sha"]):
                raise ValueError("兼容性记录必须固定完整 Git SHA")
            return GitCommit(data["sha"])
        case "pypi-sdist":
            require_keys(data, {"kind", "sha256"}, "兼容性源码")
            if not re.fullmatch(r"[a-f0-9]{64}", data["sha256"]):
                raise ValueError("兼容性记录必须固定 sdist SHA-256")
            return SdistArchive(data["sha256"])
        case _:
            raise ValueError("未知的兼容性源码类型")


def upstream_unsupported(data: dict) -> UpstreamUnsupported:
    require_keys(
        data, {"library", "python", "source", "detail", "evidence"}, "上游不兼容记录"
    )
    if not data["detail"] or not data["evidence"].startswith("https://"):
        raise ValueError("上游不兼容记录必须包含说明与证据链接")
    return UpstreamUnsupported(
        data["library"],
        PythonVersion(data["python"]),
        source_identity(data["source"]),
        data["detail"],
        data["evidence"],
    )


def load_incompatibilities(path: Path) -> tuple[UpstreamUnsupported, ...]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    require_keys(data, {"unsupported"}, str(path))
    entries = tuple(upstream_unsupported(row) for row in data["unsupported"])
    keys = [(e.library, e.python, e.source) for e in entries]
    if len(keys) != len(set(keys)):
        raise ValueError("上游不兼容记录重复")
    return entries
