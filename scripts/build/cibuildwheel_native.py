"""Build target libraries before PEP 517 dependency discovery runs setup.py."""

import argparse
import os
from enum import StrEnum
from pathlib import Path

from scripts.build.android_python import AndroidABI
from scripts.build.native_cache import seal, verify
from scripts.build.native_libraries import build_libraries
from scripts.build.native_model import NativeLibrary


class Preparation(StrEnum):
    BUILD = "build"
    RESTORE = "restore"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", type=Preparation, choices=list(Preparation), required=True
    )
    parser.add_argument("--key", required=True)
    args = parser.parse_args()
    prefix = Path(os.environ["NATIVE_PREFIX"])
    if args.mode == Preparation.RESTORE:
        verify(prefix, args.key)
        return
    ndk = Path(os.environ["ANDROID_NDK"])
    build_libraries(
        tuple(
            NativeLibrary(name) for name in os.environ["NATIVE_DEPENDENCIES"].split(",")
        ),
        prefix,
        ndk,
        ndk / "toolchains/llvm/prebuilt/linux-x86_64",
        AndroidABI(os.environ["TARGET_ABI"]),
        int(os.environ["ANDROID_API"]),
    )

    seal(prefix, args.key)


if __name__ == "__main__":
    main()
