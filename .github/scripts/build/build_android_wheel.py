#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
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


SCRIPT_VERSION = "2025-10-22.v2"  # 用于日志确认脚本是否为最新


def run(cmd, **kwargs):
    print(f"$ {' '.join(map(str, cmd))}")
    return subprocess.run(cmd, check=True, **kwargs)


def which(cmd: str) -> bool:
    from shutil import which as _which
    return _which(cmd) is not None


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


def prepare_build_environment(ndk_path: Path, target_triplet: str, android_api: str) -> dict[str, str]:
    """Prepares the environment variables for cross-compilation."""
    print("--- Preparing cross-compilation environment ---")
    toolchain = ndk_path / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64"
    env = os.environ.copy()

    env["NDK_HOME"] = str(ndk_path)
    env["TOOLCHAIN"] = str(toolchain)

    # Set compiler and linker
    cc = f"{toolchain}/bin/{target_triplet}{android_api}-clang"
    cxx = f"{toolchain}/bin/{target_triplet}{android_api}-clang++"
    env["CC"] = cc
    env["CXX"] = cxx
    env["AR"] = f"{toolchain}/bin/llvm-ar"
    env["LD"] = f"{toolchain}/bin/ld"
    env["STRIP"] = f"{toolchain}/bin/llvm-strip"

    # Flags
    sysroot_flags = f"--sysroot={toolchain}/sysroot"
    env["CFLAGS"] = sysroot_flags
    env["LDFLAGS"] = sysroot_flags

    # Cargo target-specific env
    cargo_prefix = target_triplet.upper().replace("-", "_")
    env[f"CARGO_TARGET_{cargo_prefix}_LINKER"] = cc
    env[f"CARGO_TARGET_{cargo_prefix}_AR"] = env["AR"]

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
        guard = '#![cfg(any(target_arch = "x86", target_arch = "x86_64"))]'
        if guard not in txt:
            avx512.write_text(guard + "\n" + txt, encoding="utf-8")
            print("Injected cfg guard into orjson/src/str/avx512.rs")
        ok1 = guard in avx512.read_text(encoding="utf-8")

    if pystr.exists():
        txt = pystr.read_text(encoding="utf-8")
        patched = txt
        # avx512 检测
        patched = patched.replace(
            'if std::is_x86_feature_detected!("avx512vl") {',
            '#[cfg(any(target_arch = "x86", target_arch = "x86_64"))]\n        '
            'if std::is_x86_feature_detected!("avx512vl") {'
        )
        # 若还有 avx2 检测，一并守卫（不存在也无影响）
        patched = patched.replace(
            'if std::is_x86_feature_detected!("avx2") {',
            '#[cfg(any(target_arch = "x86", target_arch = "x86_64"))]\n        '
            'if std::is_x86_feature_detected!("avx2") {'
        )
        if patched != txt:
            pystr.write_text(patched, encoding="utf-8")
            print("Injected cfg guards into orjson/src/str/pystr.rs")
        ok2 = '#[cfg(any(target_arch = "x86", target_arch = "x86_64"))]' in pystr.read_text(encoding="utf-8")

    if not (ok1 and ok2):
        print("WARNING: orjson patch verification failed (one of the guards missing). Build may fail on aarch64.")


def build_wheel(
    library_name: str,
    library_source_path: Path,
    source_dir: str,
    build_env: dict[str, str],
    target_triplet: str,
    python_version: str,
) -> bool:
    """Builds the wheel, using a PEP 517-compliant process for maturin."""
    print(f"=== build_android_wheel.py SCRIPT_VERSION={SCRIPT_VERSION} ===")
    print("--- Building wheel ---")
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

    # venv + maturin
    venv_path, maturin_exe = ensure_maturin_venv(project_path)

    # rust target
    run(["rustup", "target", "add", target_triplet], cwd=project_path)

    # PyO3 交叉编译：明确声明
    build_env = build_env.copy()
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
        if any(prefix in k for prefix in ["PYO3", "CARGO_TARGET_", "CC", "CXX", "AR"]):
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
    try:
        run(build_cmd, env=build_env, cwd=project_path)
        print("构建成功完成!")
    except subprocess.CalledProcessError as e:
        print(f"构建失败，退出码: {e.returncode}")
        print("尝试使用 --find-interpreter 选项重新构建...")
        find_interpreter_cmd = [
            str(maturin_exe),
            "build",
            "--release",
            "--target", target_triplet,
            "--find-interpreter",
        ]
        run(find_interpreter_cmd, env=build_env, cwd=project_path)

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

    clone_library_source(git_repository, library_version, library_source_path)

    if os.environ.get("USE_CROSS") in ("1", "true") and CAN_USE_CROSS:
        print("--- Using cross to build wheel ---")
        is_maturin = build_wheel_with_cross(
            library_name=library_name,
            library_source_path=library_source_path,
            source_dir=source_dir,
            target_triplet=target_triplet,
            python_version=python_version,
        )
    else:
        print("--- Using default build process ---")
        setup_ndk(ndk_path, ndk_version)
        build_env = prepare_build_environment(ndk_path, target_triplet, android_api)
        is_maturin = build_wheel(
            library_name=library_name,
            library_source_path=library_source_path,
            source_dir=source_dir,
            build_env=build_env,
            target_triplet=target_triplet,
            python_version=python_version,
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
