#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
from pathlib import Path

import tomllib

from build_utils import run, which, patch_orjson_for_android, patch_pyo3_cargo_toml





def ensure_maturin_venv_and_zig(project_path: Path) -> tuple[Path, Path]:
    """
    Create an isolated venv under project and install maturin with zig support.
    """
    venv_path = project_path / ".build_venv"
    python_bin = venv_path / "bin" / "python"
    maturin_bin = venv_path / "bin" / "maturin"
    maturin_zig_dep = "maturin[zig]>=1,<2"

    if not venv_path.exists():
        print(f"Creating isolated build environment at: {venv_path}")
        if which("uv"):
            run(["uv", "venv", str(venv_path)], cwd=project_path)
            run(["uv", "pip", "install", "--python", str(python_bin), maturin_zig_dep], cwd=project_path)
        else:
            run([sys.executable, "-m", "venv", str(venv_path)], cwd=project_path)
            run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], cwd=project_path)
            run([str(python_bin), "-m", "pip", "install", maturin_zig_dep], cwd=project_path)
    else:
        # ensure maturin[zig] present
        if which("uv"):
            run(["uv", "pip", "install", "--python", str(python_bin), maturin_zig_dep], cwd=project_path)
        else:
            run([str(python_bin), "-m", "pip", "install", maturin_zig_dep], cwd=project_path)

    print(f"Using CPython interpreter at: {python_bin}")
    print(f"Using maturin at: {maturin_bin}")
    return venv_path, maturin_bin






def build_wheel_with_zig(
    library_name: str,
    library_source_path: Path,
    source_dir: str,
    target_triplet: str,
    python_version: str,
    ndk_path: Path,
    android_api: str,
) -> bool:
    """Builds the wheel using zig."""
    print(f"=== build_android_wheel.py (zig) SCRIPT_VERSION=2025-10-23.v1 ===")
    print("--- Building wheel with zig ---")
    project_path = library_source_path / source_dir
    print(f"Project path: {project_path}")

    patch_pyo3_cargo_toml(project_path)

    pyproject_path = project_path / "pyproject.toml"
    if not pyproject_path.is_file():
        raise ValueError("This build script is only for maturin-based projects.")

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    build_system = pyproject.get("build-system", {})
    backend = build_system.get("build-backend", "")

    print(f"Build backend: {backend}")
    if backend != "maturin":
        raise ValueError("This script currently only supports maturin.")

    # venv + maturin + zig
    venv_path, maturin_exe = ensure_maturin_venv_and_zig(project_path)

    # rust target
    run(["rustup", "target", "add", target_triplet], cwd=project_path)

    # Build Env
    build_env = os.environ.copy()
    build_env["ANDROID_NDK_HOME"] = str(ndk_path)
    venv_bin_path = venv_path / "bin"
    build_env["PATH"] = f"{venv_bin_path}:{build_env.get('PATH', '')}"

    # Manually set sysroot for zig, as cargo-zigbuild's auto-detection seems insufficient
    toolchain = ndk_path / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64"
    sysroot_flags = f"--sysroot={toolchain}/sysroot"
    build_env["CFLAGS"] = f"{build_env.get('CFLAGS', '')} {sysroot_flags}"
    build_env["LDFLAGS"] = f"{build_env.get('LDFLAGS', '')} {sysroot_flags}"

    # PyO3 cross-compilation
    build_env["PYO3_CROSS"] = "1"
    build_env["PYO3_CROSS_PYTHON_VERSION"] = python_version
    build_env["PYO3_CROSS_PYTHON_IMPLEMENTATION"] = build_env.get("PYO3_CROSS_PYTHON_IMPLEMENTATION", "CPython")

    if "android" in target_triplet:
        print("Android target: skipping PYO3_CROSS_LIB_DIR (official recommendation)")

    if library_name == "orjson" and ("aarch64" in target_triplet or "arm64" in target_triplet):
        patch_orjson_for_android(project_path)
        build_env.pop("RUSTFLAGS", None)
        build_env.setdefault("ORJSON_DISABLE_YYJSON", "1")

    print("Final build environment (key info):")
    for k, v in sorted(build_env.items()):
        if any(prefix in k for prefix in ["PYO3", "CARGO_TARGET_", "CC", "CXX", "AR"]):
            print(f"  {k}={v}")

    interpreter_cli = f"python{python_version}"
    if interpreter_cli.startswith("/"):
        raise RuntimeError(f"Interpreter name resolved to a path: {interpreter_cli}")

    build_cmd = [
        str(maturin_exe),
        "build",
        "--release",
        "--target", target_triplet,
        "-i", interpreter_cli,
        "--zig",
        "--compatibility", "linux",
    ]

    print(f"Using interpreter name for maturin: -i {interpreter_cli}")
    run(build_cmd, env=build_env, cwd=project_path)
    print("Build completed successfully!")

    return True
