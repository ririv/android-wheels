"""Constrain wheel compatibility to its actual Android Python dependency."""

import io
import re
import zipfile
from pathlib import Path

from elftools.elf.elffile import ELFFile
from wheel.cli.tags import tags


def python_versions(wheel: Path) -> set[str]:
    versions = set()
    with zipfile.ZipFile(wheel) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            with archive.open(entry) as stream:
                if stream.read(4) != b"\x7fELF":
                    continue
            elf = ELFFile(io.BytesIO(archive.read(entry)))
            dynamic = elf.get_section_by_name(".dynamic")
            if dynamic is None:
                continue
            for tag in dynamic.iter_tags("DT_NEEDED"):
                match = re.fullmatch(r"libpython(3\.\d+)\.so", tag.needed)
                if match:
                    versions.add(match[1])
    return versions


def constrain_abi(wheel: Path) -> Path:
    versions = python_versions(wheel)
    if len(versions) > 1:
        raise ValueError("wheel 不能依赖多个版本的 libpython")
    if not versions:
        return wheel
    version = next(iter(versions))
    _, python, abi, _ = wheel.stem.rsplit("-", 3)
    target = f"cp{version.replace('.', '')}"
    if "abi3" in abi.split("."):
        # Android 的版本专用 libpython 依赖限制了实际可加载的解释器。
        name = tags(str(wheel), python_tags=target, abi_tags=target, remove=True)
        return wheel.with_name(name)
    if python != target or abi != target:
        raise ValueError(f"wheel 标签与 libpython{version}.so 不一致")
    return wheel
