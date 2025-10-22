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
            tool.chmod(tool.stat().st_mode | 0o111)


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
    print(f"Project path: {project_path}")

    is_maturin = False
    build_system = {}
    pyproject_path = project_path / "pyproject.toml"
    if pyproject_path.is_file():
        print("pyproject.toml found. Using it to determine build backend.")
        pyproject_content = tomllib.loads(pyproject_path.read_text())
        build_system = pyproject_content.get("build-system", {})
        print(f"Build backend: {build_system.get('build-backend')}")
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

        # 使用虚拟环境中的 Python 解释器
        python_interpreter = venv_path / "bin" / "python"
        
        # 构建命令 - 使用虚拟环境中的 Python 解释器
        build_cmd = [
            str(maturin_executable), 
            "build", 
            "--release", 
            "--target", target_triplet, 
            "-i", str(python_interpreter)
        ]

        # 根据官方文档设置交叉编译环境变量
        build_env["PYO3_CROSS"] = "1"
        build_env["PYO3_CROSS_PYTHON_VERSION"] = python_version
        
        # 关键修复：对于 Android 目标，避免设置 PYO3_CROSS_LIB_DIR
        # 根据文档，对于 Unix 目标可以省略这个变量
        if "android" in target_triplet:
            print("Android 目标检测到，使用简化交叉编译配置")
            # 不设置 PYO3_CROSS_LIB_DIR，让 PyO3 使用默认配置

        # 对于orjson的特殊处理
        if library_name == "orjson":
            print("使用 orjson 特定的构建配置")
            
            # 禁用 yyjson 以避免 C 依赖编译问题
            print("为 Android 禁用 yyjson 以避免 C 依赖编译问题")
            build_env["ORJSON_DISABLE_YYJSON"] = "1"
            
            # 移除有问题的 RUSTFLAGS，使用默认设置
            if "RUSTFLAGS" in build_env:
                del build_env["RUSTFLAGS"]
            print("使用默认 RUSTFLAGS 设置")

        # 添加调试信息
        print("最终构建环境变量:")
        for key, value in sorted(build_env.items()):
            if any(prefix in key for prefix in ["PYO3", "CARGO", "CC", "CXX", "AR"]):
                print(f"  {key}={value}")

        # 执行构建命令
        print(f"执行构建命令: {' '.join(build_cmd)}")
        try:
            subprocess.run(build_cmd, env=build_env, check=True, cwd=project_path)
            print("构建成功完成!")
        except subprocess.CalledProcessError as e:
            print(f"构建失败，退出码: {e.returncode}")
            
            # 尝试使用 --find-interpreter 选项
            print("尝试使用 --find-interpreter 选项重新构建...")
            find_interpreter_cmd = [
                str(maturin_executable), 
                "build", 
                "--release", 
                "--target", target_triplet,
                "--find-interpreter"
            ]
            
            print(f"执行构建命令: {' '.join(find_interpreter_cmd)}")
            subprocess.run(find_interpreter_cmd, env=build_env, check=True, cwd=project_path)
    else:
        raise ValueError("此构建脚本仅适用于基于 maturin 的项目。")

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

    # 查找生成的 wheel 文件
    search_path = project_path / "target" / "wheels" if is_maturin else project_path / "dist"
    print(f"Searching for wheel in: {search_path}")
    
    wheel_files = list(search_path.glob("*.whl"))
    if not wheel_files:
        print("Wheel not found in primary path, searching everywhere...")
        wheel_files = list(Path.cwd().glob("**/*.whl"))

    if not wheel_files:
        raise FileNotFoundError(f"No wheel files found after build. Searched in: {search_path}")
    
    if len(wheel_files) > 1:
        print(f"Found multiple wheel files: {wheel_files}. Using the first one.")
    
    wheel_path = wheel_files[0]
    print(f"Found wheel: {wheel_path}")

    # 重命名 wheel 文件
    normalized_lib_name = library_name.replace("-", "_")
    platform_arch = target_abi.replace("-", "_")
    py_tag = f"cp{python_version.replace('.', '')}"

    version_to_use = library_version
    if not version_to_use:
        wheel_name_parts = wheel_path.name.split("-")
        if len(wheel_name_parts) >= 2:
            version_to_use = wheel_name_parts[1]
            print(f"Library version not specified, using version from wheel: {version_to_use}")
        else:
            raise ValueError(f"Cannot extract version from wheel filename: {wheel_path.name}")

    new_wheel_name = f"{normalized_lib_name}-{version_to_use}-{py_tag}-{py_tag}-android_{android_api}_{platform_arch}.whl"
    print(f"New wheel name: {new_wheel_name}")

    # 移动 wheel 文件到输出目录
    output_dir = Path.cwd().resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)
    final_wheel_path = output_dir / new_wheel_name
    shutil.move(wheel_path, final_wheel_path)
    print(f"Moved wheel to: {final_wheel_path}")


def main():
    # 读取环境变量
    library_name = os.environ["CIBW_LIBRARY_NAME"]
    git_repository = os.environ["CIBW_GIT_REPOSITORY"]
    library_version = os.environ.get("CIBW_LIBRARY_VERSION")
    source_dir = os.environ.get("CIBW_SOURCE_DIR", ".")
    python_version = os.environ["CIBW_PYTHON_VERSION"]
    android_api = os.environ["CIBW_ANDROID_API"]
    target_abi = os.environ["CIBW_TARGET_ABI"]
    target_triplet = os.environ["CIBW_TARGET_TRIPLET"]

    print(f"--- Building {library_name} for Android {target_abi} ---")
    print(f"Python version: {python_version}, Android API: {android_api}")

    # 常量定义
    ndk_version = "r26d"
    temp_dir = Path(os.environ.get("RUNNER_TEMP", "/tmp"))
    ndk_path = temp_dir / f"android-ndk-{ndk_version}"
    library_source_path = Path.cwd() / "library-source"

    # 设置 NDK
    setup_ndk(ndk_path, ndk_version)

    # 克隆库源码
    clone_library_source(git_repository, library_version, library_source_path)

    # 准备构建环境
    build_env = prepare_build_environment(ndk_path, target_triplet, android_api)

    # 构建 wheel
    is_maturin = build_wheel(
        library_name=library_name,
        library_source_path=library_source_path,
        source_dir=source_dir,
        build_env=build_env,
        target_triplet=target_triplet,
        python_version=python_version,
    )

    # 处理生成的 wheel 文件
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