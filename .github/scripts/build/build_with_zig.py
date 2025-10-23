#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
from pathlib import Path

import tomllib


def run(cmd, **kwargs):
    print(f"$ {' '.join(map(str, cmd))}")
    return subprocess.run(cmd, check=True, **kwargs)


def which(cmd: str) -> bool:
    from shutil import which as _which
    return _which(cmd) is not None


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


def patch_orjson_for_android(project_path: Path) -> None:
    """
    在非 x86 目标上为 orjson 打最小补丁，避免编译 x86/AVX 代码：
    1) 给 src/str/avx512.rs 整文件加 x86/x86_64 cfg 守卫；
    2) 给 src/str/pystr.rs 中 is_x86_feature_detected! 调用加 cfg 守卫。
    """
    print("--- Patching orjson sources for non-x86 targets ---")
    str_dir = project_path / "src" / "str"
    avx512 = str_dir / "avx512.rs"
    pystr = str_dir / "pystr.rs"

    ok1 = ok2 = False

    if avx512.exists():
        txt = avx512.read_text(encoding="utf-8")
        guard = '''#![cfg(any(target_arch = "x86", target_arch = "x86_64"))]'''
        if guard not in txt:
            avx512.write_text(guard + "\n" + txt, encoding="utf-8")
            print("Injected cfg guard into orjson/src/str/avx512.rs")
        ok1 = guard in avx512.read_text(encoding="utf-8")

    if pystr.exists():
        txt = pystr.read_text(encoding="utf-8")
        patched = txt
        # avx512 检测
        patched = patched.replace(
            '''if std::is_x86_feature_detected!(\"avx512vl\") {''',
            '''#[cfg(any(target_arch = "x86", target_arch = "x86_64"))]\n        if std::is_x86_feature_detected!(\"avx512vl\") {'''
        )
        # 若还有 avx2 检测，一并守卫（不存在也无影响）
        patched = patched.replace(
            '''if std::is_x86_feature_detected!(\"avx2\") {''',
            '''#[cfg(any(target_arch = "x86", target_arch = "x86_64"))]\n        if std::is_x86_feature_detected!(\"avx2\") {'''
        )
        if patched != txt:
            pystr.write_text(patched, encoding="utf-8")
            print("Injected cfg guards into orjson/src/str/pystr.rs")
        ok2 = '''#[cfg(any(target_arch = "x86", target_arch = "x86_64"))]''' in pystr.read_text(encoding="utf-8")

    if not (ok1 and ok2):
        print("WARNING: orjson patch verification failed (one of the guards missing). Build may fail on aarch64.")


def build_wheel_with_zig(
    library_name: str,
    library_source_path: Path,
    source_dir: str,
    target_triplet: str,
    python_version: str,
) -> bool:
    """Builds the wheel using zig."""
    print(f"=== build_android_wheel.py (zig) SCRIPT_VERSION=2025-10-23.v1 ===")
    print("--- Building wheel with zig ---")
    project_path = library_source_path / source_dir
    print(f"Project path: {project_path}")

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
    venv_bin_path = venv_path / "bin"
    build_env["PATH"] = f"{venv_bin_path}:{build_env.get('PATH', '')}"

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
