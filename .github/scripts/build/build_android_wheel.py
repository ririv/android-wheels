#!/usr/bin/env python3

import os
import subprocess
import sys

from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import tomllib


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
    
    # After unpacking, the directory is named android-ndk-r26d, so we rename it
    unpacked_dir = ndk_path.parent / f"android-ndk-{ndk_version}"
    unpacked_dir.rename(ndk_path)

    print("Cleaning up NDK zip...")
    ndk_zip_path.unlink()

    print("Adding execute permissions to NDK toolchain...")
    toolchain_bin_path = ndk_path / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64" / "bin"
    for tool in toolchain_bin_path.glob("*"):
        if not tool.is_dir():
            tool.chmod(tool.stat().st_mode | 0o111) # Add execute permission for user, group, and others


def clone_library_source(repo_url: str, version: str | None, path: Path):
    """Clones the library source code from the given repository."""
    print(f"--- Cloning {repo_url} ---")
    if path.exists():
        print("Library source directory already exists. Skipping clone.")
        return

    cmd = ["git", "clone", "--depth=1"]
    if version:
        cmd.extend(["--branch", version])
    cmd.extend([f"https://github.com/{repo_url}.git", str(path)])
    
    subprocess.run(cmd, check=True)
    subprocess.run(["git", "submodule", "update", "--init", "--recursive"], cwd=path, check=True)


def prepare_build_environment(ndk_path: Path, target_triplet: str, android_api: str) -> dict[str, str]:
    """Prepares the environment variables for cross-compilation."""
    print("--- Preparing cross-compilation environment ---")
    toolchain_path = ndk_path / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64"
    env = os.environ.copy()

    env["NDK_HOME"] = str(ndk_path)
    env["TOOLCHAIN"] = str(toolchain_path)

    # Set compiler and linker
    env["CC"] = f"{toolchain_path}/bin/{target_triplet}{android_api}-clang"
    env["CXX"] = f"{toolchain_path}/bin/{target_triplet}{android_api}-clang++"
    env["AR"] = f"{toolchain_path}/bin/llvm-ar"
    env["LD"] = f"{toolchain_path}/bin/ld"
    env["STRIP"] = f"{toolchain_path}/bin/llvm-strip"

    # Set flags
    sysroot_flags = f"--sysroot={toolchain_path}/sysroot"
    env["CFLAGS"] = sysroot_flags
    env["LDFLAGS"] = sysroot_flags

    # Set cargo target-specific environment variables
    cargo_target_env_prefix = target_triplet.upper().replace("-", "_")
    env[f"CARGO_TARGET_{cargo_target_env_prefix}_LINKER"] = env["CC"]
    env[f"CARGO_TARGET_{cargo_target_env_prefix}_AR"] = env["AR"]

    return env


def build_wheel(
    library_name: str,
    library_source_path: Path,
    source_dir: str,
    build_env: dict[str, str],
    target_triplet: str,
    python_version: str,
) -> bool:
    """Builds the wheel, using a PEP 517-compliant process for maturin."""
    print("--- Building wheel ---")

    project_path = library_source_path / source_dir

    is_maturin = False
    build_system = {}
    pyproject_path = Path("pyproject.toml")
    if pyproject_path.is_file():


        pyproject_content = tomllib.loads(pyproject_path.read_text())
        build_system = pyproject_content.get("build-system", {})
        if build_system.get("build-backend") == "maturin":
            is_maturin = True

    if is_maturin:
        print("Maturin build backend detected. Using isolated build environment.")
        
        build_requires = build_system.get("requires", ["maturin"])
        venv_path = project_path / ".build_venv"
        print(f"Creating isolated build environment at {venv_path}...")
        subprocess.run(["uv", "venv", str(venv_path)], check=True, cwd=project_path)
        print(f"Installing build dependencies: {build_requires}")
        uv_pip_cmd = [
            "uv", "pip", "install", 
            "--python", str(venv_path / "bin" / "python"),
        ] + build_requires
        subprocess.run(uv_pip_cmd, check=True, cwd=project_path)
        
        maturin_executable = venv_path / "bin" / "maturin"

        subprocess.run(["rustup", "target", "add", target_triplet], check=True, cwd=project_path)

        build_cmd = [str(maturin_executable), "build", "--release", "--target", target_triplet, "-i", f"python{python_version}"]

        if library_name == "orjson":
            print("Applying orjson-specific workaround: disabling AVX512.")
            build_env["ORJSON_DISABLE_AVX512"] = "1"

        cargo_path = project_path / "Cargo.toml"
        if cargo_path.is_file():
            cargo_content = cargo_path.read_text()
            if any(line.strip().startswith("pyo3 ") for line in cargo_content.splitlines()):
                print("Direct pyo3 dependency found. Adding 'extension-module' feature.")
                build_cmd.extend(["--features", "pyo3/extension-module"])
        
        print(f"Executing build command: {' '.join(build_cmd)}")
        subprocess.run(build_cmd, env=build_env, check=True, cwd=project_path)
    else:
        print("Standard build backend detected. Using `python -m build`.")
        subprocess.run([sys.executable, "-m", "build", "--wheel", "--no-isolation", str(project_path)], env=build_env, check=True)

    return is_maturin


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

    # --- Find Wheel --- #
    search_path = project_path / "target" / "wheels" if is_maturin else project_path / "dist"
    print(f"Searching for wheel in: {search_path}")
    
    wheel_files = list(search_path.glob("*.whl"))
    if not wheel_files:
        # Fallback search
        print("Wheel not found in primary path, searching everywhere...")
        wheel_files = list(Path.cwd().glob("**/*.whl"))

    if len(wheel_files) != 1:
        raise FileNotFoundError(f"Expected 1 wheel file, but found {len(wheel_files)}: {wheel_files}")
    
    wheel_path = wheel_files[0]
    print(f"Found wheel: {wheel_path}")

    # --- Rename Wheel --- #
    normalized_lib_name = library_name.replace("-", "_")
    platform_arch = target_abi.replace("-", "_")
    py_tag = f"cp{python_version.replace('.', '')}"

    version_to_use = library_version
    if not version_to_use:
        # Extract version from wheel filename, e.g., orjson-3.11.3-cp313-cp313-win_amd64.whl
        version_to_use = wheel_path.name.split("-")[1]
        print(f"Library version not specified, using version from wheel: {version_to_use}")

    new_wheel_name = f"{normalized_lib_name}-{version_to_use}-{py_tag}-{py_tag}-android_{android_api}_{platform_arch}.whl"
    print(f"New wheel name: {new_wheel_name}")

    # --- Move Wheel --- #
    output_dir = Path.cwd().resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)
    final_wheel_path = output_dir / new_wheel_name
    shutil.move(wheel_path, final_wheel_path)
    print(f"Moved wheel to: {final_wheel_path}")


def main():
    # --- Read environment variables --- #
    library_name = os.environ["CIBW_LIBRARY_NAME"]
    git_repository = os.environ["CIBW_GIT_REPOSITORY"]
    library_version = os.environ.get("CIBW_LIBRARY_VERSION") # Optional
    source_dir = os.environ.get("CIBW_SOURCE_DIR", ".")
    python_version = os.environ["CIBW_PYTHON_VERSION"]
    android_api = os.environ["CIBW_ANDROID_API"]
    target_abi = os.environ["CIBW_TARGET_ABI"]
    target_triplet = os.environ["CIBW_TARGET_TRIPLET"]

    print(f"--- Building {library_name} for Android {target_abi} ---")
    print(f"Python version: {python_version}, Android API: {android_api}")

    # --- Constants --- #
    ndk_version = "r26d"
    # In GitHub Actions, runner.temp is typically /home/runner/work/_temp
    temp_dir = Path(os.environ.get("RUNNER_TEMP", "/tmp"))
    ndk_path = temp_dir / f"android-ndk-{ndk_version}"
    library_source_path = Path.cwd() / "library-source"

    # --- Setup NDK --- #
    setup_ndk(ndk_path, ndk_version)

    # --- Clone library source --- #
    clone_library_source(git_repository, library_version, library_source_path)

    # --- Prepare build environment --- #
    build_env = prepare_build_environment(ndk_path, target_triplet, android_api)

    # --- Build wheel --- #
    is_maturin = build_wheel(
        library_name=library_name,
        library_source_path=library_source_path,
        source_dir=source_dir,
        build_env=build_env,
        target_triplet=target_triplet,
        python_version=python_version,
    )

    # --- Process wheel --- #
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
