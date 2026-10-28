"""Build target libraries before PEP 517 dependency discovery runs setup.py."""

import os
from pathlib import Path

from scripts.build.android_python import AndroidABI
from scripts.build.native_libraries import build_libraries
from scripts.build.native_model import NativeLibrary


def main() -> None:
    ndk = Path(os.environ["ANDROID_NDK"])
    build_libraries(
        tuple(NativeLibrary(name) for name in os.environ["NATIVE_DEPENDENCIES"].split(",")),
        Path(os.environ["NATIVE_PREFIX"]),
        ndk,
        ndk / "toolchains/llvm/prebuilt/linux-x86_64",
        AndroidABI(os.environ["TARGET_ABI"]),
        int(os.environ["ANDROID_API"]),
    )


if __name__ == "__main__":
    main()
