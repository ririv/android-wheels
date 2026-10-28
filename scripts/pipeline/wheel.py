"""Verify PEP 427 filename tags, internal metadata and every RECORD entry."""

import base64
import csv
import hashlib
import io
import json
import re
import zipfile
from email.parser import BytesParser
from itertools import product
from pathlib import Path

from elftools.elf.elffile import ELFFile
from packaging.specifiers import SpecifierSet

from scripts.build.native_libraries import library_specs
from scripts.build.wheel_alignment import verify_alignment
from scripts.pipeline.model import SdistSource, Target


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def tag_set(python: str, abi: str, platform: str) -> set[str]:
    return {
        "-".join(tag)
        for tag in product(python.split("."), abi.split("."), platform.split("."))
    }


def verify_record(archive: zipfile.ZipFile, record_name: str) -> None:
    files = [info.filename for info in archive.infolist() if not info.is_dir()]
    if len(set(files)) != len(files):
        raise ValueError("wheel 存在重复 ZIP 文件条目")
    rows = list(csv.reader(io.StringIO(archive.read(record_name).decode("utf-8"))))
    if any(len(row) != 3 for row in rows):
        raise ValueError("RECORD 必须包含三列")
    records = {row[0]: (row[1], row[2]) for row in rows}
    if len(records) != len(rows):
        raise ValueError("RECORD 存在重复文件条目")
    signatures = {record_name + ".jws", record_name + ".p7s"}
    if set(records) != set(files) - signatures:
        raise ValueError("RECORD 文件集合与 ZIP 内容不一致")
    for name, (encoded, size) in records.items():
        if name == record_name:
            if encoded or size:
                raise ValueError("RECORD 自身的哈希与大小必须为空")
            continue
        algorithm, expected = encoded.split("=", 1)
        digest = hashlib.new(algorithm)
        if digest.digest_size < 32:
            raise ValueError(f"RECORD 使用了不受支持的弱哈希：{algorithm}")
        length = 0
        with archive.open(name) as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                length += len(chunk)
        actual = base64.urlsafe_b64encode(digest.digest()).rstrip(b"=").decode("ascii")
        if actual != expected or str(length) != size:
            raise ValueError(f"RECORD 哈希或大小不匹配：{name}")


def verify_wheel(path: Path, target: Target) -> None:
    match path.stem.split("-"):
        case [name, version, python, abi, platform]:
            pass
        case [name, version, build, python, abi, platform] if re.match(r"\d", build):
            pass
        case _:
            raise ValueError(f"无效的 wheel 文件名：{path.name}")
    if normalized(name) != normalized(target.library):
        raise ValueError(f"wheel 包名不匹配：{path.name}")
    if isinstance(
        target.source, SdistSource
    ) and version != target.source.version.replace("-", "_"):
        raise ValueError("wheel 版本与固定的 PyPI 发行版本不一致")
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
        metadata_files = [
            n for n in archive.namelist() if n.endswith(".dist-info/METADATA")
        ]
        if len(metadata_files) != 1:
            raise ValueError("wheel 必须包含唯一 METADATA")
        prefix = metadata_files[0].removesuffix("METADATA")
        metadata = BytesParser().parsebytes(archive.read(prefix + "METADATA"))
        if (
            normalized(metadata["Name"]) != normalized(target.library)
            or metadata["Version"].replace("-", "_") != version
        ):
            raise ValueError(f"wheel 元数据不匹配：{path}")
        if not SpecifierSet(metadata.get("Requires-Python", "")).contains(
            target.python.value
        ):
            raise ValueError("wheel Requires-Python 不支持构建目标")
        if target.native_dependencies:
            specs = library_specs(
                Path(__file__).parents[1] / "build" / "native-libraries.toml"
            )
            expected = [specs[name].to_dict() for name in target.native_dependencies]
            if json.loads(archive.read(prefix + "native-libraries.json")) != expected:
                raise ValueError("wheel 原生依赖来源与固定配置不一致")
            for name in target.native_dependencies:
                for license_file in specs[name].licenses:
                    if not archive.read(
                        prefix + f"licenses/native/{name}/{license_file}"
                    ):
                        raise ValueError("原生依赖许可证不能为空")
        wheel_name, record_name = prefix + "WHEEL", prefix + "RECORD"
        if not {wheel_name, record_name}.issubset(archive.namelist()):
            raise ValueError("wheel 必须包含 WHEEL 和 RECORD")
        wheel = BytesParser().parsebytes(archive.read(wheel_name))
        internal = set()
        for tag in wheel.get_all("Tag", []):
            internal.update(tag_set(*tag.split("-")))
        if internal != tag_set(python, abi, platform):
            raise ValueError("WHEEL 标签与文件名不一致")
        if wheel["Wheel-Version"] != "1.0":
            raise ValueError("不支持的 Wheel-Version")
        verify_record(archive, record_name)
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            with archive.open(entry) as stream:
                if stream.read(4) == b"\x7fELF":
                    data = archive.read(entry)
                    expected_machine = {
                        "arm64-v8a": "EM_AARCH64",
                        "x86_64": "EM_X86_64",
                    }[target.abi.value]
                    elf = ELFFile(io.BytesIO(data))
                    if elf.header["e_machine"] != expected_machine:
                        raise ValueError(f"ELF 架构与目标不一致：{entry.filename}")
                    verify_alignment(io.BytesIO(data), entry.filename)
