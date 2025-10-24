#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
from pathlib import Path

from build_utils import run, patch_orjson_for_android, patch_pyo3_cargo_toml


def build_native_library_with_cross(
    library_name: str,
    library_source_path: Path,
    source_dir: str,
    target_triplet: str,
    python_version: str,
    python_lib_dir: Path,
    module_name: str,
) -> Path:
    """Builds the native .so library using cross, without maturin."""
    print(f"=== build_native_library_with_cross.py SCRIPT_VERSION=2025-10-24.v1 ===")
    print("--- Building native library with cross ---")
    project_path = library_source_path / source_dir
    print(f"Project path: {project_path}")

    # 1. Install cross and add rust target
    run(["cargo", "install", "cross", "--git", "https://github.com/cross-rs/cross"], cwd=project_path)
    run(["rustup", "target", "add", target_triplet], cwd=project_path)

    # 2. Patch Cargo.toml to ensure it builds a pyo3 extension module
    patch_pyo3_cargo_toml(project_path)

    # 3. Prepare the comprehensive build environment
    build_env = os.environ.copy()

    # Tell cargo to use the `cross` command
    build_env["CARGO"] = "cross"

    # --- PyO3 cross-compilation environment variables ---
    build_env["PYO3_CROSS"] = "1"
    build_env["PYO3_CROSS_PYTHON_VERSION"] = python_version

    # Set the sysconfigdata directory and name
    sysconfigdata_dir = python_lib_dir / f"python{python_version}"
    if not sysconfigdata_dir.is_dir():
        raise FileNotFoundError(f"Sysconfigdata directory not found at {sysconfigdata_dir}")

    sysconfig_files = list(sysconfigdata_dir.glob("_sysconfigdata*.py"))
    if not sysconfig_files:
        raise FileNotFoundError(f"No '_sysconfigdata*.py' file found in {sysconfigdata_dir}")
    sysconfig_file_name = sysconfig_files[0].name

    build_env["_PYTHON_SYSCONFIGDATA_NAME"] = sysconfig_file_name.removesuffix(".py")
    build_env["PYO3_CROSS_LIB_DIR"] = str(sysconfigdata_dir)

    # --- Linker environment variables for rustc ---
    cargo_rustflags_key = f"CARGO_TARGET_{target_triplet.upper().replace('-', '_')}_RUSTFLAGS"
    linker_args = [
        f"-L{python_lib_dir}",
        f"-lpython{python_version}"
    ]
    rustflags = " ".join([f"-C link-arg={arg}" for arg in linker_args])
    build_env[cargo_rustflags_key] = f"{build_env.get(cargo_rustflags_key, '')} {rustflags}".strip()

    # --- Special patches for specific libraries ---
    if library_name == "orjson" and ("aarch64" in target_triplet or "arm64" in target_triplet):
        patch_orjson_for_android(project_path)
        build_env.pop("RUSTFLAGS", None)
        build_env.setdefault("ORJSON_DISABLE_YYJSON", "1")

    # 4. Run the build command
    print("--- Running cargo build with cross ---")
    build_cmd = [
        "cross",
        "build",
        "--release",
        "--target", target_triplet,
    ]
    run(build_cmd, env=build_env, cwd=project_path)

    # 5. Find and return the path to the compiled .so file
    print("--- Locating compiled .so file ---")
    # The name of the .so file is derived from the module name in pyproject.toml
    # We need to convert it to the correct format (e.g., `my_module` -> `libmy_module.so`)
    so_filename = f"lib{module_name.replace('-', '_')}.so"
    artifact_path = project_path / "target" / target_triplet / "release" / so_filename

    if not artifact_path.exists():
        raise FileNotFoundError(f"Could not find compiled library at {artifact_path}")

    print(f"Successfully built native library: {artifact_path}")

    # To make it a valid python extension, it needs to be renamed
    # e.g. libjiter_python.so -> jiter_python.so
    final_so_path = artifact_path.parent / f"{module_name}.so"
    shutil.move(artifact_path, final_so_path)
    print(f"Renamed artifact to {final_so_path}")

    return final_so_path
