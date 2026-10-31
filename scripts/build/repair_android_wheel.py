#!/usr/bin/env python3
"""Android repair step for cibuildwheel.

cibuildwheel v4 repairs Android wheels with `auditwheel repair`, which rejects
wheels that contain no ELF files. Some projects fall back to pure Python when
their optional C extension can't be built (e.g. PyYAML without libyaml), so
such wheels are passed through unchanged, as cibuildwheel v3 did.

Usage: repair_android_wheel.py <wheel> <dest_dir> <ldpaths>
"""

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from scripts.build.link_flags import PAGE_SIZE
from scripts.build.wheel_abi import constrain_abi
from scripts.build.wheel_native import attach_native_metadata
from scripts.build.wheel_rpath import normalize_rpaths


def contains_elf(wheel: str) -> bool:
    with zipfile.ZipFile(wheel) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            with zf.open(info) as f:
                if f.read(4) == b"\x7fELF":
                    return True
    return False


def repair(wheel: str, dest_dir: str, ldpaths: str) -> None:
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    if contains_elf(wheel):
        paths = ldpaths.split(os.pathsep)
        if os.environ["NATIVE_DEPENDENCIES"]:
            paths.insert(0, str(Path(os.environ["NATIVE_PREFIX"]) / "lib"))
        cmd = [
            "auditwheel",
            "repair",
            "--ldpaths",
            os.pathsep.join(dict.fromkeys(paths)),
            "-w",
            dest_dir,
            wheel,
        ]
        # auditwheel 的 patchelf 接口未提供页大小参数；固定 CLI 适配器保留新加载段对齐。
        real_patchelf = shutil.which("patchelf")
        if real_patchelf is None:
            raise FileNotFoundError("找不到 patchelf")
        with tempfile.TemporaryDirectory(prefix="android-patchelf-") as temporary:
            adapter = Path(temporary) / "patchelf"
            adapter.write_text(
                "#!/bin/sh\nexec "
                + shlex.quote(real_patchelf)
                + f' --page-size {PAGE_SIZE} "$@"\n',
                encoding="utf-8",
            )
            adapter.chmod(0o755)
            subprocess.run(
                cmd,
                env={**os.environ, "PATH": temporary + os.pathsep + os.environ["PATH"]},
                check=True,
            )
        repaired = list(Path(dest_dir).glob("*.whl"))
        if len(repaired) != 1:
            raise ValueError("Android repair 必须生成恰好一个 wheel")
        normalize_rpaths(repaired[0])
        attach_native_metadata(repaired[0])
        constrain_abi(repaired[0])
        return

    print(f"{wheel} contains no ELF files, skipping auditwheel repair")
    shutil.copy2(wheel, dest_dir)


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(f"usage: {sys.argv[0]} <wheel> <dest_dir> <ldpaths>")
    repair(*sys.argv[1:])


if __name__ == "__main__":
    main()
