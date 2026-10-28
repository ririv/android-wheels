#!/usr/bin/env python3
"""Android repair step for cibuildwheel.

cibuildwheel v4 repairs Android wheels with `auditwheel repair`, which rejects
wheels that contain no ELF files. Some projects fall back to pure Python when
their optional C extension can't be built (e.g. PyYAML without libyaml), so
such wheels are passed through unchanged, as cibuildwheel v3 did.

Usage: repair_android_wheel.py <wheel> <dest_dir> <ldpaths>
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from scripts.build.wheel_abi import constrain_abi
from scripts.build.wheel_native import attach_native_metadata


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
        cmd = ["auditwheel", "repair", "--ldpaths", ldpaths, "-w", dest_dir, wheel]
        subprocess.run(cmd, check=True)
        repaired = list(Path(dest_dir).glob("*.whl"))
        if len(repaired) != 1:
            raise ValueError("Android repair 必须生成恰好一个 wheel")
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
