#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
import tarfile
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import tomllib

try:
    from build_with_cross import build_wheel_with_cross
    CAN_USE_CROSS = True
except ImportError:
    CAN_USE_CROSS = False

try:
    from build_with_zig import build_wheel_with_zig
    CAN_USE_ZIG = True
except ImportError:
    CAN_USE_ZIG = False

from build_utils import run, which, patch_pyo3_cargo_toml, patch_orjson_for_android, create_cargo_config


SCRIPT_VERSION = "2025-10-22.v2"  # 用于日志确认脚本是否为最新








def setup_ndk(ndk_path: Path, ndk_version: str):
    """Checks if NDK is cached, otherwise downloads and extracts it."""
    print(f"--- Setting up Android NDK {ndk_version} ---")
    if ndk_path.exists():
        print("NDK found in cache.")
        return

    print("NDK not found, downloading...")
    ndk_zip_path = ndk_path.with_suffix(".zip")
    ndk_url = f"https://dl.google.com/android/repository/android-ndk-{ndk_version}-linux.zip"
    urllib.request.urlretrieve(ndk_url, ndk_zip_path)

    print("Extracting NDK...")
    shutil.unpack_archive(ndk_zip_path, ndk_path.parent)

    unpacked_dir = ndk_path.parent / f"android-ndk-{ndk_version}"
    unpacked_dir.rename(ndk_path)

    print("Cleaning up NDK zip...")
    ndk_zip_path.unlink(missing_ok=True)

    print("Adding execute permissions to NDK toolchain...")
    toolchain_bin_path = ndk_path / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64" / "bin"
    for tool in toolchain_bin_path.glob("*"):
        if tool.is_file():
            tool.chmod(tool.stat().st_mode | 0o111)


def clone_library_source(repo_url: str, version: str | None, path: Path):
    """Clones the library source code from the given repository."""
    print(f"--- Cloning {repo_url} ---")
    if path.exists():
        print("Library source directory already exists. Skipping clone.")
        return

    cmd = ["git", "clone", "--depth=1"]
    if version:
        cmd += ["--branch", version]
    cmd += [f"https://github.com/{repo_url}.git", str(path)]
    run(cmd)
    run(["git", "submodule", "update", "--init", "--recursive"], cwd=path)


def get_latest_patch_for_python(python_version: str) -> str:
    """
    Finds the latest patch version for a given Python major.minor version
    by querying the GitHub API for CPython tags, handling pagination.
    Returns the full X.Y.Z version string.
    """
    print(f"--- Finding latest patch for Python {python_version} from GitHub API ---")

    patch_versions = []
    # Start with the first page, fetching max items per page
    url = "https://api.github.com/repos/python/cpython/tags?per_page=100"

    while url:
        print(f"Fetching tags from: {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "android-wheels-script"})
            with urllib.request.urlopen(req, timeout=15) as response:
                tags_data = json.load(response)

                # Process tags on the current page
                version_prefix = f"v{python_version}."
                for tag in tags_data:
                    tag_name = tag.get("name", "")
                    if tag_name.startswith(version_prefix):
                        try:
                            patch_num = int(tag_name[1:].split('.')[-1])
                            patch_versions.append(patch_num)
                        except (ValueError, IndexError):
                            continue

                # Check for next page in Link header
                link_header = response.headers.get('Link')
                url = None  # Assume no next page unless we find one
                if link_header:
                    links = link_header.split(',')
                    for link in links:
                        parts = link.split(';')
                        if len(parts) == 2 and parts[1].strip() == 'rel="next"':
                            url = parts[0].strip()[1:-1]  # Remove < and >
                            break

        except Exception as e:
            print(f"Warning: Could not fetch Python tags from GitHub API: {e}")
            # If we fail at any point, it's safer to fallback than to use partial data
            print("Falling back to assuming '.0' patch version.")
            return f"{python_version}.0"

    if not patch_versions:
        print(f"Warning: No patch versions found for {python_version} via GitHub API.")
        print("Falling back to assuming '.0' patch version.")
        return f"{python_version}.0"

    latest_patch = max(patch_versions)
    full_version = f"{python_version}.{latest_patch}"
    print(f"Found latest patch version via API after checking all pages: {full_version}")
    return full_version


def setup_python_cross_build(
    download_path: Path,
    python_version: str,  # e.g. 3.13
    target_triplet: str,  # e.g. aarch64-linux-android
) -> Path:
    """Downloads and extracts pre-built CPython for cross-compilation."""
    print(f"--- Setting up pre-built Python {python_version} for {target_triplet} ---")

    # Per user instruction, the final library path is always in this structure.
    lib_dir = download_path / "prefix" / "lib"

    # Caching check: if the final lib directory exists, assume it's valid and skip everything.
    if lib_dir.is_dir():
        print(f"Found cached pre-built Python lib directory at {lib_dir}")
        return lib_dir

    # --- If not cached, proceed with download and extraction ---

    major_str, minor_str = python_version.split('.')
    major, minor = int(major_str), int(minor_str)

    full_python_version = ""
    download_url = ""
    file_name = ""

    if minor < 13:
        raise ValueError(f"Python < 3.13 is not supported for pre-built downloads. Please build it yourself.")
    elif minor == 13:
        print("Python 3.13: Using pre-built from ririv/android-wheels.")
        python_version_map = {"3.13": "3.13.9"}
        full_python_version = python_version_map.get(python_version)
        if not full_python_version:
            raise ValueError(f"Could not determine full version for Python {python_version}")
        file_name = f"python-{full_python_version}-{target_triplet}.tar.gz"
        download_url = f"https://raw.githubusercontent.com/ririv/android-wheels/cpython-android/{python_version}/{file_name}"
    else:  # minor >= 14
        print("Python >= 3.14: Using pre-built from python.org.")
        full_python_version = get_latest_patch_for_python(python_version)
        file_name = f"python-{full_python_version}-{target_triplet}.tar.gz"
        download_url = f"https://www.python.org/ftp/python/{full_python_version}/{file_name}"

    archive_path = download_path / file_name
    if not archive_path.exists():
        print(f"Downloading from {download_url}...")
        try:
            urllib.request.urlretrieve(download_url, archive_path)
        except urllib.error.HTTPError as e:
            print(f"Failed to download: {e}")
            if minor >= 14 and e.code == 404:
                print(f"Could not find version {full_python_version} on python.org.")
                print("Please check the python.org FTP for the correct version and update the script if scraping failed.")
            raise

    print(f"Extracting {archive_path} to {download_path}")
    shutil.unpack_archive(archive_path, download_path)

    # Final check: The lib directory MUST exist now.
    if not lib_dir.is_dir():
        raise FileNotFoundError(f"Could not locate 'prefix/lib' directory at {lib_dir} after extraction.")

    print(f"Found pre-built Python lib dir: {lib_dir}")
    return lib_dir

def prepare_build_environment(ndk_path: Path, target_triplet: str, android_api: str) -> dict[str, str]:
    """Prepares the environment variables for cross-compilation."""
    print("--- Preparing cross-compilation environment ---")
    toolchain = ndk_path / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64"
    env = os.environ.copy()

    # Add NDK toolchain to PATH for auto-discovery by rustc and other tools
    toolchain_bin = toolchain / "bin"
    env["PATH"] = f"{toolchain_bin}:{os.environ['PATH']}"

    # Set compiler env vars for C/C++ build scripts (e.g. in dependencies).
    # Since the toolchain bin is in the PATH, we can just use the names.
    env["CC"] = f"{target_triplet}{android_api}-clang"
    env["CXX"] = f"{target_triplet}{android_api}-clang++"
    env["AR"] = "llvm-ar"

    # Set sysroot flags for the C/C++ compilers
    sysroot_flags = f"--sysroot={toolchain}/sysroot"
    env["CFLAGS"] = sysroot_flags
    env["LDFLAGS"] = sysroot_flags

    # Let rustc find the linker from the PATH.
    # We only need to hint the AR, which is a common practice.
    cargo_prefix = target_triplet.upper().replace("-", "_")
    env[f"CARGO_TARGET_{cargo_prefix}_AR"] = "llvm-ar"

    return env


def ensure_maturin_venv(project_path: Path) -> tuple[Path, Path]:
    """
    Create an isolated venv under project and install maturin.
    Prefer uv, fall back to python -m venv + pip.
    Returns (venv_path, maturin_exe_path).
    """
    venv_path = project_path / ".build_venv"
    python_bin = venv_path / "bin" / "python"
    maturin_bin = venv_path / "bin" / "maturin"

    if not venv_path.exists():
        print(f"Creating isolated build environment at: {venv_path}")
        if which("uv"):
            run(["uv", "venv", str(venv_path)], cwd=project_path)
            run(["uv", "pip", "install", "--python", str(python_bin), "maturin>=1,<2"], cwd=project_path)
        else:
            # fallback to stdlib venv + pip
            run([sys.executable, "-m", "venv", str(venv_path)], cwd=project_path)
            run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], cwd=project_path)
            run([str(python_bin), "-m", "pip", "install", "maturin>=1,<2"], cwd=project_path)
    else:
        # ensure maturin present
        if not maturin_bin.exists():
            if which("uv"):
                run(["uv", "pip", "install", "--python", str(python_bin), "maturin>=1,<2"], cwd=project_path)
            else:
                run([str(python_bin), "-m", "pip", "install", "maturin>=1,<2"], cwd=project_path)

    print(f"Using CPython interpreter at: {python_bin}")
    print(f"Using maturin at: {maturin_bin}")
    return venv_path, maturin_bin







def build_wheel(
    library_name: str,
    library_source_path: Path,
    source_dir: str,
    build_env: dict[str, str],
    target_triplet: str,
    python_version: str,
    android_api: str,
    python_lib_dir: Path,
) -> bool:
    """Builds the wheel, using a PEP 517-compliant process for maturin."""
    print(f"=== build_android_wheel.py SCRIPT_VERSION={SCRIPT_VERSION} ===")
    print("--- Building wheel ---")
    project_path = library_source_path / source_dir
    print(f"Project path: {project_path}")

    # patch_pyo3_cargo_toml(project_path)
    create_cargo_config(project_path, target_triplet, android_api)

    pyproject_path = project_path / "pyproject.toml"
    if not pyproject_path.is_file():
        raise ValueError("此构建脚本仅适用于基于 maturin 的项目（需要 pyproject.toml 且 build-backend = 'maturin'）。")

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    build_system = pyproject.get("build-system", {})
    backend = build_system.get("build-backend", "")

    print(f"Build backend: {backend}")
    if backend != "maturin":
        raise ValueError("检测到非 maturin 后端；此脚本当前仅支持 maturin。")

    # venv + maturin
    venv_path, maturin_exe = ensure_maturin_venv(project_path)

    # rust target
    run(["rustup", "target", "add", target_triplet], cwd=project_path)

    # PyO3 交叉编译：明确声明
    build_env = build_env.copy()
    build_env["PYO3_CROSS"] = "1"
    build_env["PYO3_CROSS_PYTHON_VERSION"] = python_version
    build_env["PYO3_CROSS_PYTHON_IMPLEMENTATION"] = build_env.get("PYO3_CROSS_PYTHON_IMPLEMENTATION", "CPython")

    # 为 Android 目标设置 PYO3_CROSS_LIB_DIR
    if "android" in target_triplet:
        build_env["PYO3_CROSS_LIB_DIR"] = str(python_lib_dir)
        print(f"PYO3_CROSS_LIB_DIR set to: {python_lib_dir}")

    # orjson 的 aarch64 补丁（构建前强制执行并校验）
    if library_name == "orjson" and ("aarch64" in target_triplet or "arm64" in target_triplet):
        patch_orjson_for_android(project_path)
        # 避免人为设置的 RUSTFLAGS 里强开 x86 特性
        build_env.pop("RUSTFLAGS", None)
        # 可选：减少 C 依赖触发（如果上游支持该开关则生效；不支持也无碍）
        build_env.setdefault("ORJSON_DISABLE_YYJSON", "1")

    # Add verbose linker flag for diagnostics
    print("--- Adding verbose linker flag for diagnostics ---")
    verbose_linker_flag = "-C link-arg=-Wl,-v"
    build_env["RUSTFLAGS"] = f"{build_env.get('RUSTFLAGS', '')} {verbose_linker_flag}"

    # 仅打印关键交叉编译环境
    print("最终构建环境变量（关键信息）：")
    for k, v in sorted(build_env.items()):
        if any(prefix in k for prefix in ["PYO3", "CARGO_TARGET_", "CC", "CXX", "AR"]):
            print(f"  {k}={v}")

    # maturin 构建：❗交叉编译 -i 必须是“解释器名”，不能是绝对路径
    interpreter_cli = f"python{python_version}"  # e.g. python3.13
    if interpreter_cli.startswith("/"):
        raise RuntimeError(f"内部防护：解释器名被解析成了路径：{interpreter_cli}")

    build_cmd = [
        str(maturin_exe),
        "build",
        # "--verbose",
        "--release",
        "--target", target_triplet,
        # "-i", interpreter_cli,
    ]

    print(f"将使用解释器名传给 maturin: -i {interpreter_cli}")
    run(build_cmd, env=build_env, cwd=project_path)

    return True


def process_wheel(
    library_name: str,
    library_version: str | None,
    project_path: Path,
    is_maturin: bool,
    python_version: str,
    android_api: str,
    target_abi: str,
):
    """Finds, renames, and moves the built wheel to the output directory."""
    print("--- Processing built wheel ---")

    search_path = project_path / "target" / "wheels" if is_maturin else project_path / "dist"
    print(f"Searching for wheel in: {search_path}")

    wheel_files = list(search_path.glob("*.whl"))
    if not wheel_files:
        print("Wheel not found in primary path, searching everywhere...")
        wheel_files = list(Path(project_path).glob("**/*.whl"))

    if not wheel_files:
        raise FileNotFoundError(f"No wheel files found after build. Searched in: {search_path}")

    wheel_path = sorted(wheel_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    print(f"Found wheel: {wheel_path}")

    normalized_lib_name = library_name.replace("-", "_")
    platform_arch = target_abi.replace("-", "_")
    py_tag = f"cp{python_version.replace('.', '')}"

    version_to_use = library_version
    if not version_to_use:
        # name-version-...
        parts = wheel_path.name.split("-")
        if len(parts) >= 2:
            version_to_use = parts[1]
            print(f"Library version not specified, using version from wheel: {version_to_use}")
        else:
            raise ValueError(f"Cannot extract version from wheel filename: {wheel_path.name}")

    new_wheel_name = f"{normalized_lib_name}-{version_to_use}-{py_tag}-{py_tag}-android_{android_api}_{platform_arch}.whl"
    print(f"New wheel name: {new_wheel_name}")

    output_dir = Path.cwd().resolve().parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    final_wheel_path = output_dir / new_wheel_name
    shutil.move(str(wheel_path), final_wheel_path)
    print(f"Moved wheel to: {final_wheel_path}")


def main():
    # 读取环境变量（与现有 CI 对齐）
    library_name = os.environ["CIBW_LIBRARY_NAME"]
    git_repository = os.environ["CIBW_GIT_REPOSITORY"]
    library_version = os.environ.get("CIBW_LIBRARY_VERSION")
    source_dir = os.environ.get("CIBW_SOURCE_DIR", ".")
    python_version = os.environ["CIBW_PYTHON_VERSION"]  # e.g. "3.13"
    android_api = os.environ["CIBW_ANDROID_API"]        # e.g. "24"
    target_abi = os.environ["CIBW_TARGET_ABI"]          # e.g. "arm64-v8a"
    target_triplet = os.environ["CIBW_TARGET_TRIPLET"]  # e.g. "aarch64-linux-android"

    print(f"--- Building {library_name} for Android {target_abi} ---")
    print(f"Python version: {python_version}, Android API: {android_api}")

    ndk_version = "r26d"
    temp_dir = Path(os.environ.get("RUNNER_TEMP", "/tmp"))
    ndk_path = temp_dir / f"android-ndk-{ndk_version}"
    library_source_path = Path.cwd() / "library-source"

    python_lib_dir = setup_python_cross_build(
        download_path=temp_dir,
        python_version=python_version,
        target_triplet=target_triplet,
    )

    setup_ndk(ndk_path, ndk_version)
    clone_library_source(git_repository, library_version, library_source_path)

    build_method = os.environ.get("BUILD_METHOD", "native").lower()

    if build_method == "zig" and CAN_USE_ZIG:
        print("--- Using zig to build wheel ---")
        is_maturin = build_wheel_with_zig(
            library_name=library_name,
            library_source_path=library_source_path,
            source_dir=source_dir,
            target_triplet=target_triplet,
            python_version=python_version,
            ndk_path=ndk_path,
            android_api=android_api,
        )
    elif build_method == "cross" and CAN_USE_CROSS:
        print("--- Using cross to build wheel ---")
        is_maturin = build_wheel_with_cross(
            library_name=library_name,
            library_source_path=library_source_path,
            source_dir=source_dir,
            target_triplet=target_triplet,
            python_version=python_version,
        )
    else:
        print("--- Using default native build process ---")
        setup_ndk(ndk_path, ndk_version)
        build_env = prepare_build_environment(ndk_path, target_triplet, android_api)
        is_maturin = build_wheel(
            library_name=library_name,
            library_source_path=library_source_path,
            source_dir=source_dir,
            build_env=build_env,
            target_triplet=target_triplet,
            python_version=python_version,
            android_api=android_api,
            python_lib_dir=python_lib_dir,
        )

    process_wheel(
        library_name=library_name,
        library_version=library_version,
        project_path=library_source_path / source_dir,
        is_maturin=is_maturin,
        python_version=python_version,
        android_api=android_api,
        target_abi=target_abi,
    )


if __name__ == "__main__":
    main()
