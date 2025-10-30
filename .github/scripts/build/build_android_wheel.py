#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import tomllib
from shutil import which
from build_utils import patch_pyo3_cargo_toml, create_cargo_config
import urllib.error



def run(cmd, **kwargs):
    print(f"$ {' '.join(map(str, cmd))}", flush=True)
    return subprocess.run(cmd, check=True, **kwargs)


def set_github_env(name: str, value: str):
    """Sets an environment variable for subsequent steps in a GitHub Actions job."""
    os.environ[name] = value

    github_env = os.getenv("GITHUB_ENV")
    if github_env:
        with open(github_env, "a") as f:
            f.write(f"{name}={value}\n")
        print(f"Env var set in $GITHUB_ENV: {name}={value}", flush=True)
    else:
        print(f"Warning: GITHUB_ENV not found. Cannot set env var {name}.", file=sys.stderr, flush=True)


def setup_ndk(ndk_path: Path, ndk_version: str):
    """Checks if NDK is cached, otherwise downloads and extracts it."""
    print(f"--- Setting up Android NDK {ndk_version} ---", flush=True)
    if ndk_path.exists():
        print("NDK found in cache.", flush=True)
        return

    print("NDK not found, downloading...", flush=True)
    ndk_zip_path = ndk_path.with_suffix(".zip")
    ndk_url = f"https://dl.google.com/android/repository/android-ndk-{ndk_version}-linux.zip"
    urllib.request.urlretrieve(ndk_url, ndk_zip_path)

    print("Extracting NDK...", flush=True)
    shutil.unpack_archive(ndk_zip_path, ndk_path.parent)

    unpacked_dir = ndk_path.parent / f"android-ndk-{ndk_version}"
    unpacked_dir.rename(ndk_path)

    print("Cleaning up NDK zip...", flush=True)
    ndk_zip_path.unlink(missing_ok=True)

    print("Adding execute permissions to NDK toolchain...", flush=True)
    toolchain_bin_path = ndk_path / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64" / "bin"
    for tool in toolchain_bin_path.glob("*"):
        if tool.is_file():
            tool.chmod(tool.stat().st_mode | 0o111)


def clone_library_source(repo_url: str, version: str | None, path: Path):
    """Clones the library source code from the given repository."""
    print(f"--- Cloning {repo_url} ---", flush=True)
    if path.exists():
        print("Library source directory already exists. Skipping clone.", flush=True)
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
    print(f"--- Finding latest patch for Python {python_version} from GitHub API ---", flush=True)

    patch_versions = []
    # Start with the first page, fetching max items per page
    url = "https://api.github.com/repos/python/cpython/tags?per_page=100"

    while url:
        print(f"Fetching tags from: {url}", flush=True)
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
            print(f"Warning: Could not fetch Python tags from GitHub API: {e}", flush=True)
            # If we fail at any point, it's safer to fallback than to use partial data
            print("Falling back to assuming '.0' patch version.", flush=True)
            return f"{python_version}.0"

    if not patch_versions:
        print(f"Warning: No patch versions found for {python_version} via GitHub API.", flush=True)
        print("Falling back to assuming '.0' patch version.", flush=True)
        return f"{python_version}.0"

    latest_patch = max(patch_versions)
    full_version = f"{python_version}.{latest_patch}"
    print(f"Found latest patch version via API after checking all pages: {full_version}", flush=True)
    return full_version


def setup_python_cross_build(
    download_path: Path,
    python_version: str,  # e.g. 3.13
    target_triplet: str,  # e.g. aarch64-linux-android
) -> Path:
    """Downloads and extracts pre-built CPython for cross-compilation."""
    print(f"--- Setting up pre-built Python {python_version} for {target_triplet} ---", flush=True)

    # Per user instruction, the final library path is always in this structure.
    lib_dir = download_path / "prefix" / "lib"

    # Caching check: if the final lib directory exists, assume it's valid and skip everything.
    if lib_dir.is_dir():
        print(f"Found cached pre-built Python lib directory at {lib_dir}", flush=True)
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
        print("Python 3.13: Using pre-built from ririv/android-wheels.", flush=True)
        python_version_map = {"3.13": "3.13.9"}
        full_python_version = python_version_map.get(python_version)
        if not full_python_version:
            raise ValueError(f"Could not determine full version for Python {python_version}")
        file_name = f"python-{full_python_version}-{target_triplet}.tar.gz"
        download_url = f"https://raw.githubusercontent.com/ririv/android-wheels/cpython-android/{python_version}/{file_name}"
    else:  # minor >= 14
        print("Python >= 3.14: Using pre-built from python.org.", flush=True)
        full_python_version = get_latest_patch_for_python(python_version)
        file_name = f"python-{full_python_version}-{target_triplet}.tar.gz"
        download_url = f"https://www.python.org/ftp/python/{full_python_version}/{file_name}"

    archive_path = download_path / file_name
    if not archive_path.exists():
        print(f"Downloading from {download_url}...", flush=True)
        try:
            urllib.request.urlretrieve(download_url, archive_path)
        except urllib.error.HTTPError as e:
            print(f"Failed to download: {e}", flush=True)
            if minor >= 14 and e.code == 404:
                print(f"Could not find version {full_python_version} on python.org.", flush=True)
                print("Please check the python.org FTP for the correct version and update the script if scraping failed.", flush=True)
            raise

    print(f"Extracting {archive_path} to {download_path}", flush=True)
    shutil.unpack_archive(archive_path, download_path)

    # Final check: The lib directory MUST exist now.
    if not lib_dir.is_dir():
        raise FileNotFoundError(f"Could not locate 'prefix/lib' directory at {lib_dir} after extraction.")

    print(f"Found pre-built Python lib dir: {lib_dir}", flush=True)
    return lib_dir

def prepare_build_environment(ndk_path: Path, target_triplet: str, android_api: str, python_version, python_lib_dir: Path) -> dict[str, str]:
    """Prepares the environment variables for cross-compilation."""
    print("--- Preparing cross-compilation environment ---", flush=True)
    toolchain = ndk_path / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64"
    # env = os.environ.copy()
    env = {}

    # Add NDK toolchain to PATH for auto-discovery by rustc and other tools
    toolchain_bin = toolchain / "bin"
    env["PATH"] = f'{toolchain_bin}:{os.environ['PATH']}'

    # Set compiler env vars for C/C++ build scripts (e.g. in dependencies).
    # Since the toolchain bin is in the PATH, we can just use the names.
    env["CC"] = str(toolchain_bin / f"{target_triplet}{android_api}-clang")
    env["CXX"] = str(toolchain_bin / f"{target_triplet}{android_api}-clang++")
    AR = str(toolchain_bin / f"{target_triplet}{android_api}-ar")
    env["AR"] = AR

    # Set sysroot flags for the C/C++ compilers
    sysroot_flags = f"--sysroot={toolchain}/sysroot"
    env["CFLAGS"] = sysroot_flags
    env["LDFLAGS"] = sysroot_flags

    # Let rustc find the linker from the PATH.
    # We only need to hint the AR, which is a common practice.
    cargo_prefix = target_triplet.upper().replace("-", "_")
    env[f"CARGO_TARGET_{cargo_prefix}_AR"] = AR
    env["CARGO_BUILD_TARGET"] = target_triplet

    env["PYO3_CROSS"] = "1"
    # env["PYO3_CROSS_PYTHON_VERSION"] = python_version
    # env["PYO3_CROSS_LIB_DIR"] = str(python_lib_dir)

    cargo_rustflags_key = f"CARGO_TARGET_{target_triplet.upper().replace('-', '_')}_RUSTFLAGS"
    linker_args = [
        f"-L{python_lib_dir}",
        f"-lpython{python_version}"
    ]
    rustflags = " ".join([f"-C link-arg={arg}" for arg in linker_args])

    env[cargo_rustflags_key] = rustflags
    for k,v in env.items():
        set_github_env(k, v)

    print("Prepared build environment variables.", flush=True)
    return env


def ensure_maturin_venv(project_path: Path) -> Path:
    """
    Ensures maturin is installed using pipx.
    Returns a dummy venv path and the path to the maturin executable.
    """
    print("--- Ensuring maturin is installed via pipx ---", flush=True)

    if not which("pipx"):
        raise RuntimeError("pipx is not installed or not in PATH. Please install pipx to continue.")

    # Check if maturin is already installed by pipx
    result = subprocess.run(["pipx", "list", "--json"], capture_output=True, text=True)
    maturin_installed = False
    if result.returncode == 0:
        try:
            pipx_list = json.loads(result.stdout)
            if "maturin" in pipx_list["venvs"]:
                maturin_installed = True
                print("maturin is already installed by pipx.", flush=True)
        except (json.JSONDecodeError, KeyError):
            print("Warning: Could not parse pipx list output. Assuming maturin is not installed.", flush=True)

    if not maturin_installed:
        print("Installing maturin with pipx...", flush=True)
        run(["pipx", "install", "maturin>=1,<2"])

    # Get maturin path
    maturin_path_str = which("maturin")
    if not maturin_path_str:
        raise RuntimeError("Failed to find maturin even after pipx installation.")

    maturin_path = Path(maturin_path_str)
    print(f"Using maturin at: {maturin_path}", flush=True)

    # The first element of the tuple (venv_path) is not used by the caller.
    # We return the project_path as a placeholder.
    return maturin_path


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
    print("--- Building wheel ---", flush=True)
    project_path = library_source_path / source_dir
    print(f"Project path: {project_path}", flush=True)

    patch_pyo3_cargo_toml(project_path)
    create_cargo_config(project_path, target_triplet, android_api, python_lib_dir, python_version)

    pyproject_path = project_path / "pyproject.toml"
    if not pyproject_path.is_file():
        raise ValueError("此构建脚本仅适用于基于 maturin 的项目（需要 pyproject.toml 且 build-backend = 'maturin'）。")

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    build_system = pyproject.get("build-system", {})
    backend = build_system.get("build-backend", "")

    print(f"Build backend: {backend}", flush=True)
    if backend != "maturin":
        raise ValueError("检测到非 maturin 后端；此脚本当前仅支持 maturin。" )

    # maturin
    maturin_exe = ensure_maturin_venv(project_path)

    # rust target
    run(["rustup", "target", "add", target_triplet], cwd=project_path)



    # maturin 构建：❗交叉编译 -i 必须是“解释器名”，不能是绝对路径
    interpreter_cli = f"python{python_version}"  # e.g. python3.13
    if interpreter_cli.startswith("/"):
        raise RuntimeError(f"内部防护：解释器名被解析成了路径：{interpreter_cli}")

    build_cmd = [
        str(maturin_exe),
        "build",
        "--verbose",
        "--release",
        "--target", target_triplet,
        "-i", interpreter_cli,
    ]
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
    print("--- Processing built wheel ---", flush=True)

    search_path = project_path / "target" / "wheels" if is_maturin else project_path / "dist"
    print(f"Searching for wheel in: {search_path}", flush=True)

    wheel_files = list(search_path.glob("*.whl"))
    if not wheel_files:
        print("Wheel not found in primary path, searching everywhere...", flush=True)
        wheel_files = list(Path(project_path).glob("**/*.whl"))

    if not wheel_files:
        raise FileNotFoundError(f"No wheel files found after build. Searched in: {search_path}")

    wheel_path = sorted(wheel_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    print(f"Found wheel: {wheel_path}", flush=True)

    normalized_lib_name = library_name.replace("-", "_")
    platform_arch = target_abi.replace("-", "_")
    py_tag = f"cp{python_version.replace('.', '')}"

    version_to_use = library_version
    if not version_to_use:
        # name-version-...
        parts = wheel_path.name.split("-")
        if len(parts) >= 2:
            version_to_use = parts[1]
            print(f"Library version not specified, using version from wheel: {version_to_use}", flush=True)
        else:
            raise ValueError(f"Cannot extract version from wheel filename: {wheel_path.name}")

    new_wheel_name = f"{normalized_lib_name}-{version_to_use}-{py_tag}-{py_tag}-android_{android_api}_{platform_arch}.whl"
    print(f"New wheel name: {new_wheel_name}", flush=True)

    output_dir = Path.cwd().resolve().parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    final_wheel_path = output_dir / new_wheel_name
    shutil.move(str(wheel_path), final_wheel_path)
    print(f"Moved wheel to: {final_wheel_path}", flush=True)


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

    print(f"--- Building {library_name} for Android {target_abi} ---", flush=True)
    print(f"Python version: {python_version}, Android API: {android_api}", flush=True)

    ndk_version = "r26d"
    temp_dir = Path(os.environ.get("RUNNER_TEMP", "/tmp"))
    ndk_path = temp_dir / f"android-ndk-{ndk_version}"
    library_source_path = Path.cwd() / "library-source"

    python_lib_dir = setup_python_cross_build(
        download_path=temp_dir,
        python_version=python_version,
        target_triplet=target_triplet,
    )
    clone_library_source(git_repository, library_version, library_source_path)

    print("--- Using default native build process ---", flush=True)
    setup_ndk(ndk_path, ndk_version)
    build_env = prepare_build_environment(ndk_path, target_triplet, android_api, python_version, python_lib_dir)

    print("PYO3_CROSS_LIB_DIR =", build_env.get("PYO3_CROSS_LIB_DIR"), flush=True)

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