"""Prepare the explicit host tools and target prefix used by cibuildwheel."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from scripts.build.android_python import AndroidABI
from scripts.build.native_libraries import build_libraries
from scripts.build.native_model import NativeLibrary
from scripts.tooling import configuration, requirements


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--venv", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    args = parser.parse_args()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            *requirements("shared", configuration()["dependency-groups"]),
        ],
        check=True,
    )
    prefix = (args.venv.parent / "python" / "prefix").resolve(strict=True)
    names = tuple(
        NativeLibrary(name)
        for name in os.environ["NATIVE_DEPENDENCIES"].split(",")
        if name
    )
    build_libraries(
        names,
        prefix,
        Path(os.environ["ANDROID_NDK"]),
        args.toolchain,
        AndroidABI(os.environ["TARGET_ABI"]),
        int(os.environ["ANDROID_API"]),
    )
    # tomli-w 由上面的固定 shared 依赖组安装，之后再加载 Cargo 配置模块。
    from scripts.pipeline.cargo_env import configure

    configure(args.project, args.venv)


if __name__ == "__main__":
    main()
