"""Verify an explicit Android runtime dependency set before installation."""

import zipfile
from email.parser import BytesParser
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

from scripts.build.android_python import PYTHON_ARCHIVES
from scripts.pipeline.artifacts import artifact_wheel, digest
from scripts.pipeline.model import Target, load_plan
from scripts.pipeline.wheel import tag_set, verify_record, verify_wheel


def native_dependency(plan: Path, artifact: Path, target: Target) -> Path:
    dependency = load_plan(plan).target(artifact.name)
    if (dependency.python, dependency.abi) != (
        target.python,
        target.abi,
    ) or dependency.api > target.api:
        raise ValueError("运行依赖的 Python、ABI 或 API 与目标不一致")
    wheel = artifact_wheel(artifact, dependency)
    verify_wheel(wheel, dependency)
    return wheel


def pure_dependency(wheel: Path, sha256: str, target: Target) -> Path:
    if digest(wheel) != sha256:
        raise ValueError(f"纯 Python 依赖哈希不一致：{wheel.name}")
    name, version, _, tags = parse_wheel_filename(wheel.name)
    if not all(tag.platform == "any" and tag.abi == "none" for tag in tags):
        raise ValueError("纯 Python 依赖必须为 any/none wheel")
    with zipfile.ZipFile(wheel) as archive:
        metadata_files = [
            n for n in archive.namelist() if n.endswith(".dist-info/METADATA")
        ]
        if len(metadata_files) != 1:
            raise ValueError("依赖必须包含唯一 METADATA")
        prefix = metadata_files[0].removesuffix("METADATA")
        metadata = BytesParser().parsebytes(archive.read(prefix + "METADATA"))
        if (
            canonicalize_name(metadata["Name"]) != name
            or Version(metadata["Version"]) != version
        ):
            raise ValueError("依赖文件名与元数据不一致")
        if not SpecifierSet(metadata.get("Requires-Python", "")).contains(
            target.python.value
        ):
            raise ValueError("依赖不支持目标 Python")
        header = BytesParser().parsebytes(archive.read(prefix + "WHEEL"))
        internal = set().union(
            *(tag_set(*tag.split("-")) for tag in header.get_all("Tag", []))
        )
        if internal != {str(tag) for tag in tags} or not any(
            tag.interpreter in {"py3", f"py{target.python.value.replace('.', '')}"}
            for tag in tags
        ):
            raise ValueError("依赖 Python 标签不匹配")
        verify_record(archive, prefix + "RECORD")
        if any(
            archive.read(n)[:4] == b"\x7fELF"
            for n in archive.namelist()
            if not n.endswith("/")
        ):
            raise ValueError("纯 Python 依赖包含 ELF")
    return wheel


def verify_closure(wheels: tuple[Path, ...], target: Target) -> list[dict]:
    packages = {}
    requirements = []
    report = []
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            metadata = BytesParser().parsebytes(
                archive.read(
                    next(
                        n
                        for n in archive.namelist()
                        if n.endswith(".dist-info/METADATA")
                    )
                )
            )
        name = canonicalize_name(metadata["Name"])
        if name in packages:
            raise ValueError(f"重复的运行依赖：{name}")
        packages[name] = Version(metadata["Version"])
        requirements.extend(
            (name, Requirement(value))
            for value in metadata.get_all("Requires-Dist", [])
        )
        report.append(
            {
                "package": name,
                "version": str(packages[name]),
                "wheel": wheel.name,
                "sha256": digest(wheel),
            }
        )
    release = PYTHON_ARCHIVES[target.python].release.partition("-")[0]
    environment = {
        **default_environment(),
        "python_version": target.python.value,
        "python_full_version": release,
        "implementation_version": release,
        "implementation_name": "cpython",
        "platform_python_implementation": "CPython",
        "os_name": "posix",
        "sys_platform": "android",
        "platform_system": "Android",
        "platform_machine": {"arm64-v8a": "aarch64", "x86_64": "x86_64"}[
            target.abi.value
        ],
        "extra": "",
    }
    for owner, requirement in requirements:
        if requirement.marker and not requirement.marker.evaluate(environment):
            continue
        installed = packages.get(canonicalize_name(requirement.name))
        if (
            requirement.url
            or installed is None
            or installed not in requirement.specifier
        ):
            raise ValueError(f"运行依赖不满足：{owner} → {requirement}")
    return report
