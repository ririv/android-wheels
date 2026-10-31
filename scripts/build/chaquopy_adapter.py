"""Compose Chaquopy environment preparation with the shared wheel pipeline."""

import importlib.util
import os
import sys
from pathlib import Path

from scripts.build.android_python import PythonVersion, write_pyo3_config
from scripts.build.link_flags import PAGE_LINK_FLAGS, rust_link_flags
from scripts.build.native_libraries import build_libraries
from scripts.build.pep517_settings import ConfiguredBuilder, backend_settings
from scripts.pipeline.model import Target


def prepare_builder(pypi: Path, target: Target):
    specification = importlib.util.spec_from_file_location(
        "chaquopy_build", pypi / "build-wheel.py"
    )
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    builder = module.BuildWheel()
    create_host = builder.create_host_env
    create_build = builder.create_build_env
    common_environment = builder.get_common_env_vars
    rust_environment = builder.get_rust_env_vars

    def create_host_env():
        create_host()
        prefix = Path(builder.host_env) / "chaquopy"
        ndk = Path(os.environ["ANDROID_NDK"])
        toolchain = ndk / "toolchains/llvm/prebuilt/linux-x86_64"
        build_libraries(
            target.native_dependencies, prefix, ndk, toolchain, target.abi, target.api
        )

    def create_build_env():
        builder.builder = ConfiguredBuilder(
            builder.builder, backend_settings(target.config_settings)
        )
        create_build()

    def get_common_env_vars(env):
        common_environment(env)
        env["LDFLAGS"] += " " + " ".join(PAGE_LINK_FLAGS)
        prefix = Path(builder.host_env) / "chaquopy"
        env["PKG_CONFIG_PATH"] = str(prefix / "lib/pkgconfig")
        env["PKG_CONFIG_ALLOW_CROSS"] = "1"
        env["NATIVE_PREFIX"] = str(prefix)
        # 使用当前编译器的 NDK，而不是宿主系统路径，供后端显式探测系统库。
        sysroot = Path(env["AR"]).parent.parent / "sysroot"
        env["C_INCLUDE_PATH"] = str(sysroot / "usr/include")
        env["LIBRARY_PATH"] = str(
            sysroot / "usr/lib" / target.abi.triplet / str(target.api)
        )

    def get_rust_env_vars(env):
        declared_flags = os.environ.get("RUSTFLAGS", "")
        rust_environment(env)
        prefix = Path(builder.host_env) / "chaquopy"
        env.pop("PYO3_NO_PYTHON", None)
        env["PYO3_CONFIG_FILE"] = str(
            write_pyo3_config(prefix / "lib", PythonVersion(builder.python))
        )
        env["RUSTFLAGS"] = " ".join(
            rust_link_flags(
                declared_flags + " " + env["RUSTFLAGS"],
                (
                    "-Wl,--no-as-needed",
                    f"-lpython{builder.python}",
                    "-Wl,--as-needed",
                    *PAGE_LINK_FLAGS,
                ),
            )
        )

    # 组合上游公开准备阶段；包源码与上游 wheel 元数据由原始 PEP 517 后端管理。
    builder.create_host_env = create_host_env
    builder.create_build_env = create_build_env
    builder.get_common_env_vars = get_common_env_vars
    builder.get_rust_env_vars = get_rust_env_vars
    return builder
