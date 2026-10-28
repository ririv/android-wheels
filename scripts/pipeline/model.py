"""Represent resolved sources and independent Android build targets."""

import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.recipes.model import Backend, Publication
from scripts.recipes.plan import artifact_prefix


class Builder(StrEnum):
    MATURIN = "maturin"
    CIBUILDWHEEL = "cibuildwheel"
    CHAQUOPY = "chaquopy"


@dataclass(frozen=True)
class Source:
    repository: str
    ref: str
    sha: str
    directory: str
    backend: Backend


@dataclass(frozen=True)
class Target:
    library: str
    source: Source
    python: PythonVersion
    abi: AndroidABI
    api: int

    @property
    def builder(self) -> Builder:
        if self.source.backend == Backend.MATURIN:
            return Builder.MATURIN
        if self.python in {
            PythonVersion.PY310,
            PythonVersion.PY311,
            PythonVersion.PY312,
        }:
            return Builder.CHAQUOPY
        return Builder.CIBUILDWHEEL

    @property
    def artifact(self) -> str:
        return f"{artifact_prefix(self.library, self.python)}-{self.abi.value}"

    def row(self) -> dict:
        return {
            **asdict(self),
            "builder": self.builder.value,
            "artifact": self.artifact,
            "triplet": self.abi.triplet,
            "cibw_arch": self.abi.value.replace("-", "_"),
        }


@dataclass(frozen=True)
class Plan:
    publication: Publication
    targets: tuple[Target, ...]

    def write(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "publication": self.publication,
                    "targets": [asdict(t) for t in self.targets],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def target(self, artifact: str) -> Target:
        return next(t for t in self.targets if t.artifact == artifact)


def load_plan(path: Path) -> Plan:
    data = json.loads(path.read_text(encoding="utf-8"))
    targets = []
    for row in data["targets"]:
        source = Source(
            **{**row["source"], "backend": Backend(row["source"]["backend"])}
        )
        if not re.fullmatch(r"[a-f0-9]{40}", source.sha):
            raise ValueError("构建计划必须使用完整提交 SHA")
        targets.append(
            Target(
                row["library"],
                source,
                PythonVersion(row["python"]),
                AndroidABI(row["abi"]),
                row["api"],
            )
        )
    plan = Plan(Publication(data["publication"]), tuple(targets))
    if len({t.artifact for t in plan.targets}) != len(plan.targets):
        raise ValueError("构建计划存在重复目标")
    return plan
