"""Remove build-host search paths while preserving wheel-relative ELF loading."""

import io
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from elftools.elf.elffile import ELFFile
from wheel.wheelfile import WheelFile

from scripts.build.link_flags import PAGE_SIZE
from scripts.build.wheel_alignment import verify_alignment


def rpaths(data: bytes) -> tuple[str, ...]:
    dynamic = ELFFile(io.BytesIO(data)).get_section_by_name(".dynamic")
    if dynamic is None:
        return ()
    result = []
    for tag in dynamic.iter_tags():
        if tag.entry.d_tag == "DT_RPATH":
            result.extend(tag.rpath.split(":"))
        elif tag.entry.d_tag == "DT_RUNPATH":
            result.extend(tag.runpath.split(":"))
    return tuple(result)


def is_portable(path: str) -> bool:
    return any(
        path == origin or path.startswith(origin + "/")
        for origin in ("$ORIGIN", "${ORIGIN}")
    )


def verify_rpaths(data: bytes, name: str) -> None:
    if any(not is_portable(path) for path in rpaths(data)):
        raise ValueError(f"ELF 包含不可移植的库搜索路径：{name}")


@dataclass(frozen=True)
class RpathChange:
    file: str
    before: tuple[str, ...]
    after: tuple[str, ...]


def normalize_rpaths(wheel: Path) -> tuple[RpathChange, ...]:
    changes = []
    with tempfile.TemporaryDirectory(prefix="wheel-rpath-") as temporary:
        destination = Path(temporary) / wheel.name
        binary = Path(temporary) / "library.so"
        with (
            WheelFile(str(wheel)) as source,
            WheelFile(str(destination), "w") as output,
        ):
            for member in source.infolist():
                if member.is_dir() or member.filename.endswith(
                    (
                        ".dist-info/RECORD",
                        ".dist-info/RECORD.jws",
                        ".dist-info/RECORD.p7s",
                    )
                ):
                    continue
                data = source.read(member)
                if data[:4] == b"\x7fELF":
                    before = rpaths(data)
                    after = tuple(
                        dict.fromkeys(path for path in before if is_portable(path))
                    )
                    if any(
                        path and not path.startswith("/") and not is_portable(path)
                        for path in before
                    ):
                        raise ValueError(
                            f"不能自动处理 ELF 的相对搜索路径：{member.filename}"
                        )
                    if before != after:
                        binary.write_bytes(data)
                        subprocess.run(
                            [
                                "patchelf",
                                "--page-size",
                                str(PAGE_SIZE),
                                *(
                                    ["--set-rpath", ":".join(after)]
                                    if after
                                    else ["--remove-rpath"]
                                ),
                                str(binary),
                            ],
                            check=True,
                        )
                        data = binary.read_bytes()
                        verify_alignment(io.BytesIO(data), member.filename)
                        verify_rpaths(data, member.filename)
                        changes.append(RpathChange(member.filename, before, after))
                output.writestr(member, data)
        if changes:
            os.replace(destination, wheel)
    return tuple(changes)
