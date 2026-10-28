"""Record and verify wheel artifacts against the complete resolved plan."""

import hashlib
import json
import re
import zipfile
from dataclasses import asdict
from email.parser import BytesParser
from pathlib import Path

from scripts.pipeline.model import Plan, Target


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def verify_wheel(path: Path, target: Target) -> None:
    match path.stem.split("-"):
        case [name, version, python, abi, platform]:
            pass
        case [name, version, build, python, abi, platform]:
            if not re.match(r"\d", build):
                raise ValueError(f"wheel build tag 必须以数字开头：{path.name}")
        case _:
            raise ValueError(f"无效的 wheel 文件名：{path.name}")
    if normalized(name) != normalized(target.library):
        raise ValueError(f"wheel 包名不匹配：{path.name}")
    if platform == "any":
        if abi != "none" or "py3" not in python.split("."):
            raise ValueError(f"无效的纯 Python wheel：{path.name}")
    else:
        expected = f"android_{target.api}_{target.abi.value.replace('-', '_')}"
        if platform != expected:
            raise ValueError(f"wheel 平台不匹配：{path.name}，预期 {expected}")
        wanted = f"cp{target.python.value.replace('.', '')}"
        stable = (
            abi == "abi3"
            and re.fullmatch(r"cp\d+", python)
            and int(python[2:]) <= int(wanted[2:])
        )
        if not (python == wanted and abi == wanted or stable):
            raise ValueError(f"wheel Python/ABI 不匹配：{path.name}")
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"wheel ZIP 校验失败：{path}")
        metadata_files = [
            n for n in archive.namelist() if n.endswith(".dist-info/METADATA")
        ]
        if len(metadata_files) != 1:
            raise ValueError(f"wheel 必须包含唯一 METADATA：{path}")
        metadata = BytesParser().parsebytes(archive.read(metadata_files[0]))
        if (
            normalized(metadata["Name"]) != normalized(target.library)
            or metadata["Version"].replace("-", "_") != version
        ):
            raise ValueError(f"wheel 元数据不匹配：{path}")


def record(directory: Path, target: Target) -> None:
    wheels = sorted(directory.glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError(
            f"每个目标必须生成一个 wheel，实际为 {len(wheels)}：{directory}"
        )
    wheel = wheels[0]
    verify_wheel(wheel, target)
    (directory / "manifest.json").write_text(
        json.dumps(
            {"target": asdict(target), "wheel": wheel.name, "sha256": digest(wheel)},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def collect(directory: Path, plan: Plan) -> dict[str, Path]:
    expected = {t.artifact for t in plan.targets}
    actual = {p.name for p in directory.iterdir()}
    if not expected or actual != expected:
        raise ValueError(
            f"产物集合不完整：缺少 {sorted(expected - actual)}，多余 {sorted(actual - expected)}"
        )
    result = {}
    for target in plan.targets:
        artifact = directory / target.artifact
        manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
        if manifest["target"] != asdict(target):
            raise ValueError(f"产物来源与构建计划不匹配：{target.artifact}")
        name = manifest["wheel"]
        if Path(name).name != name or not name.endswith(".whl"):
            raise ValueError("无效的 wheel 文件名")
        if {p.name for p in artifact.iterdir()} != {"manifest.json", name}:
            raise ValueError(f"产物目录存在未声明文件：{artifact}")
        wheel = artifact / name
        if digest(wheel) != manifest["sha256"]:
            raise ValueError(f"wheel 哈希校验失败：{wheel}")
        verify_wheel(wheel, target)
        key = f"{normalized(target.library)}/{name}"
        if key in result and digest(result[key]) != digest(wheel):
            raise ValueError(f"同名 wheel 内容冲突：{key}")
        result[key] = wheel
    return result
