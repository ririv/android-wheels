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


def ensure_maturin_venv_and_cross(project_path: Path) -> tuple[Path, Path]:
    """
    Create an isolated venv under project and install maturin and cross.
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

    # Install cross
    print("--- Installing cross ---")
    run(["cargo", "install", "cross", "--git", "https://github.com/cross-rs/cross"], cwd=project_path)

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


def build_wheel_with_cross(
    library_name: str,
    library_source_path: Path,
    source_dir: str,
    target_triplet: str,
    python_version: str,
) -> bool:
    """Builds the wheel using cross."""
    print(f"=== build_android_wheel.py (cross) SCRIPT_VERSION=2025-10-22.v2 ===")
    print("--- Building wheel with cross ---")
    project_path = library_source_path / source_dir
    print(f"Project path: {project_path}")

    pyproject_path = project_path / "pyproject.toml"
    if not pyproject_path.is_file():
        raise ValueError("此构建脚本仅适用于基于 maturin 的项目（需要 pyproject.toml 且 build-backend = 'maturin'）。")

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    build_system = pyproject.get("build-system", {})
    backend = build_system.get("build-backend", "")

    print(f"Build backend: {backend}")
    if backend != "maturin":
        raise ValueError("检测到非 maturin 后端；此脚本当前仅支持 maturin。")

    # venv + maturin + cross
    venv_path, maturin_exe = ensure_maturin_venv_and_cross(project_path)

    # rust target
    run(["rustup", "target", "add", target_triplet], cwd=project_path)

    # Build Env
    build_env = os.environ.copy()
    build_env["CARGO_COMMAND"] = "cross"

    # PyO3 交叉编译：明确声明
    build_env["PYO3_CROSS"] = "1"
    build_env["PYO3_CROSS_PYTHON_VERSION"] = python_version
    build_env["PYO3_CROSS_PYTHON_IMPLEMENTATION"] = build_env.get("PYO3_CROSS_PYTHON_IMPLEMENTATION", "CPython")

    # Android 目标：不设置 PYO3_CROSS_LIB_DIR（让 PyO3 自行处理）
    if "android" in target_triplet:
        print("Android 目标：省略 PYO3_CROSS_LIB_DIR（官方推荐路径）")

    # orjson 的 aarch64 补丁（构建前强制执行并校验）
    if library_name == "orjson" and ("aarch64" in target_triplet or "arm64" in target_triplet):
        patch_orjson_for_android(project_path)
        # 避免人为设置的 RUSTFLAGS 里强开 x86 特性
        build_env.pop("RUSTFLAGS", None)
        # 可选：减少 C 依赖触发（如果上游支持该开关则生效；不支持也无碍）
        build_env.setdefault("ORJSON_DISABLE_YYJSON", "1")

    # 仅打印关键交叉编译环境
    print("最终构建环境变量（关键信息）：")
    for k, v in sorted(build_env.items()):
        if any(prefix in k for prefix in ["PYO3", "CARGO_COMMAND", "CARGO_TARGET_", "CC", "CXX", "AR"]):
            print(f"  {k}={v}")

    # maturin 构建：❗交叉编译 -i 必须是“解释器名”，不能是绝对路径
    interpreter_cli = f"python{python_version}"  # e.g. python3.13
    if interpreter_cli.startswith("/"):
        raise RuntimeError(f"内部防护：解释器名被解析成了路径：{interpreter_cli}")

    build_cmd = [
        str(maturin_exe),
        "build",
        "--release",
        "--target", target_triplet,
        "-i", interpreter_cli,
    ]

    print(f"将使用解释器名传给 maturin: -i {interpreter_cli}")
    run(build_cmd, env=build_env, cwd=project_path)
    print("构建成功完成!")

    return True
