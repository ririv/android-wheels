#!/usr/bin/env python3

import os
import shlex
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from shutil import which

import tomli_w
from wheel.cli.tags import tags

from scripts.build.android_python import (
    AndroidABI,
    PyO3ConfigRuntime,
    PythonRuntime,
    SysconfigRuntime,
    setup_python_cross_build,
)
from scripts.build.link_flags import PAGE_LINK_FLAGS, rust_link_flags
from scripts.build.maturin_settings import MaturinOptions, maturin_options
from scripts.build.native_libraries import build_libraries
from scripts.build.native_model import NativeLibrary
from scripts.build.repair_android_wheel import repair
from scripts.build.wheel_abi import constrain_abi
from scripts.pipeline.model import load_plan


def create_cargo_config(
    project_path: Path,
    target_triplet: str,
    python_lib_dir: Path,
    linker_name: str,
    python_version: str,
):
    """Creates a .cargo/config.toml file to configure the build."""
    print("--- Creating .cargo/config.toml for cross-compilation ---")
    cargo_dir = project_path / ".cargo"
    cargo_dir.mkdir(exist_ok=True)
    # 旧链接元数据中的 libgcc 展开到 NDK 的 libunwind，仅作用于当前项目。
    compatibility = cargo_dir / "android-linker"
    compatibility.mkdir(exist_ok=True)
    (compatibility / "libgcc.a").write_text("INPUT(-lunwind)\n")
    (compatibility / "libpython3.so").write_text(f"INPUT(-lpython{python_version})\n")

    print(f"Using linker {linker_name}")

    config_path = cargo_dir / "config.toml"
    existing = tomllib.loads(config_path.read_text()) if config_path.is_file() else {}
    target_config = existing.setdefault("target", {}).setdefault(target_triplet, {})
    target_config["linker"] = linker_name
    rustflags = target_config.get("rustflags", [])
    if isinstance(rustflags, str):
        rustflags = shlex.split(rustflags)
    for directory in (compatibility, python_lib_dir):
        library_flag = ["-L", str(directory)]
        if not any(rustflags[i : i + 2] == library_flag for i in range(len(rustflags))):
            rustflags.extend(library_flag)
    # extension-module/abi3 会禁用 PyO3 的自动链接；Android 必须显式保留该依赖。
    target_config["rustflags"] = rust_link_flags(
        rustflags,
        (
            "-Wl,--no-as-needed",
            f"-lpython{python_version}",
            "-Wl,--as-needed",
            *PAGE_LINK_FLAGS,
        ),
    )
    with open(config_path, "wb") as f:
        tomli_w.dump(existing, f)

    print(f"Created {config_path} with linker and direct rustflags for python lib.")


def run(cmd, **kwargs):
    print(f"$ {' '.join(map(str, cmd))}", flush=True)
    return subprocess.run(cmd, check=True, **kwargs)


def prepare_build_environment(
    ndk_path: Path,
    target_triplet: str,
    android_api: str,
    python_version: str,
    runtime: PythonRuntime,
) -> dict[str, str]:
    """Prepares the environment variables for cross-compilation."""
    print("--- Preparing cross-compilation environment ---", flush=True)
    host_toolchains = {"linux": "linux-x86_64", "darwin": "darwin-x86_64"}
    toolchain = (
        ndk_path / "toolchains" / "llvm" / "prebuilt" / host_toolchains[sys.platform]
    )
    env = os.environ.copy()

    # 将 NDK 工具链加入 PATH，供 Rust 及其依赖发现编译器。
    toolchain_bin = toolchain / "bin"
    path_entries = [str(toolchain_bin), str(Path(sys.executable).parent)]
    # actions/setup-python 提供与目标版本一致的宿主解释器。
    host_python = os.environ.get("HOST_PYTHON")
    if host_python:
        path_entries.append(str(Path(host_python).parent))
        env["PYO3_PYTHON"] = host_python
    path_entries.append(os.environ["PATH"])
    env["PATH"] = ":".join(path_entries)

    # 为依赖中的 C/C++ 构建脚本设置编译工具。
    env["CC"] = str(toolchain_bin / f"{target_triplet}{android_api}-clang")
    env["CXX"] = str(toolchain_bin / f"{target_triplet}{android_api}-clang++")
    env["AR"] = str(toolchain_bin / "llvm-ar")

    # 显式使用 NDK sysroot。
    sysroot_flags = f"--sysroot={toolchain}/sysroot"
    env["CFLAGS"] = sysroot_flags
    env["LDFLAGS"] = sysroot_flags

    env["CARGO_BUILD_TARGET"] = target_triplet
    env["ANDROID_API_LEVEL"] = android_api

    include = runtime.lib_dir.parent / "include" / f"python{python_version}"
    env["CFLAGS"] += f" -I{include}"
    env["CXXFLAGS"] = env["CFLAGS"]
    env["PYO3_CROSS"] = "1"
    env["PYO3_CROSS_PYTHON_VERSION"] = python_version
    match runtime:
        case PyO3ConfigRuntime(config_file=config_file):
            # 旧版 Chaquopy 没有 sysconfigdata，显式使用目标 ABI 配置。
            # PyO3 读取显式配置；标准 lib/pythonX.Y 路径供 CFFI 构建脚本定位目标头文件。
            cross_lib = runtime.lib_dir / f"python{python_version}"
            env["PYO3_CROSS_LIB_DIR"] = str(cross_lib)
            env["PYO3_CONFIG_FILE"] = str(config_file)
        case SysconfigRuntime(lib_dir=lib_dir):
            env.pop("PYO3_CONFIG_FILE", None)
            env["PYO3_CROSS_LIB_DIR"] = str(lib_dir)

    print("Prepared build environment variables.", flush=True)
    return env


def ensure_maturin(build_path: str) -> Path:
    """Use the maturin executable explicitly installed by the workflow."""
    maturin_path = which("maturin", path=build_path)
    if not maturin_path:
        raise RuntimeError(
            "找不到 maturin；请先安装项目 build-system.requires 指定的 maturin。"
        )
    return Path(maturin_path)


def build_wheel(
    library_source_path: Path,
    source_dir: str,
    build_env: dict[str, str],
    target_triplet: str,
    python_version: str,
    python_lib_dir: Path,
    output_dir: Path,
    options: MaturinOptions = MaturinOptions(),
) -> None:
    """Build a maturin project with an explicit Android Python runtime."""
    print("--- Building wheel ---", flush=True)
    project_path = library_source_path / source_dir
    print(f"Project path: {project_path}", flush=True)

    create_cargo_config(
        project_path, target_triplet, python_lib_dir, build_env["CC"], python_version
    )

    pyproject_path = project_path / "pyproject.toml"
    if not pyproject_path.is_file():
        raise ValueError(
            "此构建脚本仅适用于基于 maturin 的项目（需要 pyproject.toml 且 build-backend = 'maturin'）。"
        )

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    build_system = pyproject.get("build-system", {})
    backend = build_system.get("build-backend", "")

    print(f"Build backend: {backend}", flush=True)
    if backend != "maturin":
        raise ValueError("检测到非 maturin 后端；此脚本当前仅支持 maturin。")

    # 使用工作流安装的 maturin。
    maturin_exe = ensure_maturin(build_env["PATH"])

    # 安装目标 Rust 标准库。
    run(["rustup", "target", "add", target_triplet], cwd=project_path)

    # maturin 构建：❗交叉编译 -i 必须是“解释器名”，不能是绝对路径
    interpreter_cli = f"python{python_version}"  # e.g. python3.13
    # 设置了 PYO3_CROSS_LIB_DIR 时，maturin 会在宿主 PATH 中查找该解释器，用于解析目标的 sysconfigdata
    if not which(interpreter_cli, path=build_env["PATH"]):
        raise RuntimeError(
            f"宿主 PATH 中找不到 {interpreter_cli}；请通过 HOST_PYTHON 指定（CI 中由 actions/setup-python 提供）"
        )

    build_cmd = [
        str(maturin_exe),
        "build",
        "--verbose",
        "--release",
        "--target",
        target_triplet,
        "--auditwheel",
        "skip",  # 平台标签归一后，再使用统一的 Android auditwheel 修复步骤
        "--out",
        str(output_dir),
        "-i",
        interpreter_cli,
        *options.arguments(),
    ]
    run(build_cmd, env=build_env, cwd=project_path)


def process_wheel(
    wheel_dir: Path,
    python_version: str,
    android_api: str,
    target_abi: str,
    output_dir: Path,
) -> Path:
    """Finds, renames, and moves the built wheel to the output directory."""
    print("--- Processing built wheel ---", flush=True)

    search_path = wheel_dir
    print(f"Searching for wheel in: {search_path}", flush=True)

    wheel_files = list(search_path.glob("*.whl"))
    if not wheel_files:
        raise FileNotFoundError(
            f"No wheel files found after build. Searched in: {search_path}"
        )

    if len(wheel_files) != 1:
        raise ValueError(f"预期本次构建只生成一个 wheel，实际找到：{wheel_files}")
    wheel_path = wheel_files[0]
    print(f"Found wheel: {wheel_path}", flush=True)

    # 使用 wheel 工具同时更新文件名、WHEEL 与 RECORD。
    # 先保留上游 ABI，随后根据实际的版本专用动态库约束收窄标签。
    _, wheel_python, wheel_abi, wheel_platform = wheel_path.stem.rsplit("-", 3)
    if wheel_python == "py3" and wheel_abi == "none" and wheel_platform == "any":
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / wheel_path.name
        shutil.move(str(wheel_path), destination)
        return destination
    requested_tag = f"cp{python_version.replace('.', '')}"
    abi3_compatible = (
        "abi3" in wheel_abi.split(".")
        and wheel_python.startswith("cp")
        and wheel_python[2:].isdigit()
        and int(wheel_python[2:]) <= int(requested_tag[2:])
    )
    if wheel_python != requested_tag and not abi3_compatible:
        raise ValueError(
            f"wheel 的 Python 标签 {wheel_python} 与目标 {requested_tag} 不匹配"
        )
    platform_arch = target_abi.replace("-", "_")
    new_wheel_name = tags(
        str(wheel_path),
        platform_tags=f"android_{android_api}_{platform_arch}",
        remove=True,
    )
    wheel_path = constrain_abi(wheel_path.parent / new_wheel_name)
    new_wheel_name = wheel_path.name
    print(f"Android wheel: {new_wheel_name}", flush=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    final_wheel_path = output_dir / new_wheel_name
    shutil.move(str(wheel_path), final_wheel_path)
    print(f"Moved wheel to: {final_wheel_path}", flush=True)
    return final_wheel_path


def main():
    target = load_plan(Path.cwd() / "build-plan.json").target(os.environ["ARTIFACT"])
    # 读取环境变量（与现有 CI 对齐）
    library_name = os.environ["LIBRARY_NAME"]
    source_dir = os.environ["PROJECT_DIR"]
    target_python_version = os.environ["TARGET_PYTHON_VERSION"]  # e.g. "3.13"
    android_api = os.environ["ANDROID_API"]  # e.g. "24"
    abi = AndroidABI(os.environ["TARGET_ABI"])
    target_abi = abi.value
    target_triplet = abi.triplet

    print(f"--- Building {library_name} for Android {target_abi} ---", flush=True)
    print(
        f"Python version: {target_python_version}, Android API: {android_api}",
        flush=True,
    )

    # 请直接使用GitHub Actions环境变量提供的NDK
    # 自己下载的NDK（r26d）可能在链接阶段可能出现问题 clang-17: error: no input file
    ndk_home = os.environ.get("ANDROID_NDK")
    if not ndk_home:
        raise ValueError("ANDROID_NDK environment variable is not set. Cannot proceed.")
    print(
        f"--- Using Android NDK from environment variable: {ndk_home} ---", flush=True
    )
    ndk_path = Path(ndk_home)

    temp_dir = Path(os.environ.get("RUNNER_TEMP", "/tmp"))
    library_source_path = Path.cwd() / "library-source"

    runtime = setup_python_cross_build(
        download_path=temp_dir,
        python_version=target_python_version,
        target_triplet=target_triplet,
    )

    print("--- Using default native build process ---", flush=True)
    build_env = prepare_build_environment(
        ndk_path, target_triplet, android_api, target_python_version, runtime
    )

    dependencies = tuple(
        NativeLibrary(name)
        for name in os.environ["NATIVE_DEPENDENCIES"].split(",")
        if name
    )
    prefix = Path(os.environ["NATIVE_PREFIX"])
    build_libraries(
        dependencies,
        prefix,
        ndk_path,
        Path(build_env["CC"]).parent.parent,
        abi,
        int(android_api),
    )
    if dependencies:
        build_env["CPPFLAGS"] = f"-I{prefix / 'include'}"
        build_env["LDFLAGS"] += f" -L{prefix / 'lib'}"
        build_env["PKG_CONFIG_LIBDIR"] = str(prefix / "lib" / "pkgconfig")
        build_env["PKG_CONFIG_PATH"] = ""
        build_env["PKG_CONFIG_ALLOW_CROSS"] = "1"
    if NativeLibrary.OPENSSL in dependencies:
        build_env["OPENSSL_DIR"] = str(prefix)
        build_env["OPENSSL_STATIC"] = "1"

    print(f"Android Python runtime: {runtime}", flush=True)

    wheel_dir = (
        temp_dir
        / "android-wheels"
        / library_name
        / target_python_version
        / target_triplet
    )
    if wheel_dir.exists():
        shutil.rmtree(wheel_dir)
    wheel_dir.mkdir(parents=True)
    build_wheel(
        library_source_path=library_source_path,
        source_dir=source_dir,
        build_env=build_env,
        target_triplet=target_triplet,
        python_version=target_python_version,
        python_lib_dir=runtime.lib_dir,
        output_dir=wheel_dir,
        options=maturin_options(target.config_settings),
    )

    wheel = process_wheel(
        wheel_dir=wheel_dir,
        python_version=target_python_version,
        android_api=android_api,
        target_abi=target_abi,
        output_dir=wheel_dir / "tagged",
    )

    # 与 cibuildwheel 共用修复步骤，打包 NDK C++ 运行库并核对兼容标签。
    ndk_libraries = (
        Path(build_env["CC"]).parent.parent / "sysroot" / "usr" / "lib" / target_triplet
    )
    repair(
        str(wheel),
        str(Path.cwd() / "output"),
        os.pathsep.join((str(runtime.lib_dir), str(ndk_libraries))),
    )


if __name__ == "__main__":
    main()
