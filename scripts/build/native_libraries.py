"""Build pinned native libraries without modifying their source trees."""

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

from scripts.build.android_python import AndroidABI
from scripts.build.native_model import BuildSystem, Library, NativeLibrary
from scripts.pipeline.sdists import download, extract


def library_specs(path: Path) -> dict[NativeLibrary, Library]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    result = {}
    for name, row in data.items():
        if set(row) != {
            "version",
            "filename",
            "url",
            "sha256",
            "system",
            "args",
            "licenses",
        }:
            raise ValueError(f"原生依赖字段不完整：{name}")
        if Path(row["filename"]).name != row["filename"] or not re.fullmatch(
            r"[a-f0-9]{64}", row["sha256"]
        ):
            raise ValueError(f"无效的原生依赖来源：{name}")
        result[NativeLibrary(name)] = Library(
            NativeLibrary(name),
            row["version"],
            row["filename"],
            row["url"],
            row["sha256"],
            BuildSystem(row["system"]),
            tuple(row["args"]),
            tuple(row["licenses"]),
        )
    return result


def compiler_environment(
    ndk: Path, toolchain: Path, abi: AndroidABI, api: int, prefix: Path
) -> dict[str, str]:
    binary = toolchain / "bin"
    return {
        **os.environ,
        "PATH": os.pathsep.join((str(binary), os.environ["PATH"])),
        "ANDROID_NDK_ROOT": str(ndk),
        "CC": str(binary / f"{abi.triplet}{api}-clang"),
        "CXX": str(binary / f"{abi.triplet}{api}-clang++"),
        "AR": str(binary / "llvm-ar"),
        "RANLIB": str(binary / "llvm-ranlib"),
        "CFLAGS": "-O2 -fPIC",
        "CXXFLAGS": "-O2 -fPIC",
        "CPPFLAGS": f"-I{prefix / 'include'}",
        "LDFLAGS": f"-L{prefix / 'lib'}",
        "PKG_CONFIG_LIBDIR": str(prefix / "lib" / "pkgconfig"),
        "PKG_CONFIG_PATH": "",
        "PKG_CONFIG_ALLOW_CROSS": "1",
    }


def commands(
    library: Library,
    source: Path,
    build: Path,
    prefix: Path,
    ndk: Path,
    abi: AndroidABI,
    api: int,
) -> tuple[list[str], ...]:
    match library.system:
        case BuildSystem.AUTOTOOLS:
            return (
                [
                    str(source / "configure"),
                    f"--host={abi.triplet}",
                    f"--prefix={prefix}",
                    "--libdir=" + str(prefix / "lib"),
                    *library.args,
                ],
                ["make", "-j2"],
                ["make", "install"],
            )
        case BuildSystem.OPENSSL:
            target = {
                AndroidABI.ARM64: "android-arm64",
                AndroidABI.X86_64: "android-x86_64",
            }[abi]
            return (
                [
                    "perl",
                    str(source / "Configure"),
                    target,
                    f"-D__ANDROID_API__={api}",
                    f"--prefix={prefix}",
                    "--libdir=lib",
                    *library.args,
                ],
                ["make", "-j2"],
                ["make", "install_sw"],
            )
        case BuildSystem.CMAKE:
            return (
                [
                    "cmake",
                    "-S",
                    str(source),
                    "-B",
                    str(build),
                    "-DCMAKE_TOOLCHAIN_FILE="
                    + str(ndk / "build" / "cmake" / "android.toolchain.cmake"),
                    f"-DANDROID_ABI={abi.value}",
                    f"-DANDROID_PLATFORM=android-{api}",
                    f"-DCMAKE_INSTALL_PREFIX={prefix}",
                    "-DCMAKE_INSTALL_LIBDIR=lib",
                    "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
                    "-DCMAKE_BUILD_TYPE=Release",
                    *library.args,
                ],
                ["cmake", "--build", str(build), "--parallel", "2"],
                ["cmake", "--install", str(build)],
            )


def build_libraries(
    names: tuple[NativeLibrary, ...],
    prefix: Path,
    ndk: Path,
    toolchain: Path,
    abi: AndroidABI,
    api: int,
) -> None:
    if not names:
        return
    if prefix.exists():
        raise FileExistsError(f"原生依赖目录必须不存在：{prefix}")
    prefix.mkdir(parents=True)
    specs = library_specs(Path(__file__).with_name("native-libraries.toml"))
    env = compiler_environment(ndk, toolchain, abi, api, prefix)
    metadata = []
    with tempfile.TemporaryDirectory(prefix="android-native-") as temporary:
        root = Path(temporary)
        for name in names:
            library = specs[name]
            archive = download(library.url, library.sha256, root / library.filename)
            source = extract(archive, root / (name + "-source"))
            build = root / (name + "-build")
            build.mkdir()
            for command in commands(library, source, build, prefix, ndk, abi, api):
                print("编译原生依赖：", name, command, flush=True)
                subprocess.run(command, cwd=build, env=env, check=True)
            for license_file in library.licenses:
                destination = prefix / "licenses" / name / license_file
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / license_file, destination)
            metadata.append(library.to_dict())
    (prefix / "native-libraries.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--libraries", required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--ndk", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--abi", type=AndroidABI, required=True)
    parser.add_argument("--api", type=int, required=True)
    args = parser.parse_args()
    names = tuple(NativeLibrary(name) for name in args.libraries.split(",") if name)
    build_libraries(names, args.prefix, args.ndk, args.toolchain, args.abi, args.api)


if __name__ == "__main__":
    main()
