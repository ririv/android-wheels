"""Normalize host-derived extension filenames in cross-compiled wheels."""

import copy
import os
import re
import tempfile
from pathlib import Path

from wheel.wheelfile import WheelFile

HOST_SUFFIX = re.compile(r"\.cpython-\d+[a-z]*-(?:x86_64|aarch64)-linux-gnu\.so$")


def normalize_extensions(wheel: Path) -> None:
    """Use CPython's portable .so suffix without altering compiled code."""
    with tempfile.TemporaryDirectory(prefix="wheel-extensions-") as temporary:
        destination = Path(temporary) / wheel.name
        with (
            WheelFile(str(wheel)) as source,
            WheelFile(str(destination), "w") as output,
        ):
            names = set()
            for member in source.infolist():
                if member.is_dir() or member.filename.endswith(
                    (
                        ".dist-info/RECORD",
                        ".dist-info/RECORD.jws",
                        ".dist-info/RECORD.p7s",
                    )
                ):
                    continue
                name = HOST_SUFFIX.sub(".so", member.filename)
                if name in names:
                    raise ValueError(f"扩展文件名规范化后冲突：{name}")
                names.add(name)
                info = copy.copy(member)
                info.filename = name
                output.writestr(info, source.read(member))
        os.replace(destination, wheel)
