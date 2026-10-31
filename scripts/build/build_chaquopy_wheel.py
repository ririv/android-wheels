"""Build pre-3.13 Android wheels using Chaquopy's prepared PEP 517 environment."""

import os
import sys
import tempfile
import tomllib
from pathlib import Path

import yaml
from build.util import project_wheel_metadata
from packaging.requirements import Requirement

from scripts.build.android_python import (
    PYTHON_ARCHIVES,
    ChaquopyArchive,
    download_archive,
)
from scripts.build.build_android_wheel import process_wheel
from scripts.build.chaquopy_adapter import prepare_builder
from scripts.build.repair_android_wheel import repair
from scripts.build.wheel_extensions import normalize_extensions
from scripts.pipeline.model import SdistSource, load_plan


def main() -> None:
    workspace = Path.cwd()
    target = load_plan(workspace / "build-plan.json").target(os.environ["ARTIFACT"])
    version, abi = target.python, target.abi
    runtime = PYTHON_ARCHIVES[version]
    if not isinstance(runtime, ChaquopyArchive):
        raise TypeError(f"Python {version} 应使用现代 Android 构建流程")
    chaquopy = workspace / "chaquopy"
    project = workspace / "library-source" / target.source.directory
    pypi_dir = chaquopy / "server/pypi"
    target_dir = chaquopy / "maven/com/chaquo/python/target" / runtime.release
    download_archive(runtime.url(abi), target_dir)
    host_python = Path(os.environ["HOST_PYTHON"])
    os.environ["PATH"] = os.pathsep.join(
        [str(Path(sys.executable).parent), str(host_python.parent), os.environ["PATH"]]
    )

    if isinstance(target.source, SdistSource):
        name, version_string = target.source.package, target.source.version
    else:
        metadata = project_wheel_metadata(str(project), isolated=True)
        name, version_string = metadata["Name"], metadata["Version"]
    metadata_path = project / "pyproject.toml"
    requirements = (
        tomllib.loads(metadata_path.read_text())
        .get("build-system", {})
        .get("requires", [])
        if metadata_path.is_file()
        else []
    )
    rust = any(Requirement(r).name == "setuptools-rust" for r in requirements)
    recipe = {
        "package": {"name": name, "version": version_string},
        "source": {"path": str(project)},
        "requirements": {"host": ["python"], "build": ["rust"] if rust else []},
        "build": {"script_env": []},
    }
    # compiler-wrapper 只接受 Chaquopy server 目录内的依赖路径。
    with tempfile.TemporaryDirectory(
        prefix="android-wheel-recipe-", dir=pypi_dir
    ) as recipe_dir:
        (Path(recipe_dir) / "meta.yaml").write_text(
            yaml.safe_dump(recipe), encoding="utf-8"
        )
        builder = prepare_builder(pypi_dir, target, workspace)
        sys.argv = [
            str(pypi_dir / "build-wheel.py"),
            "--no-build",
            "--python",
            version.value,
            "--abi",
            abi.value,
            "--api-level",
            str(target.api),
            recipe_dir,
        ]
        builder.main()
        with builder.env_vars():
            builder.create_dummy_libs()
            wheel = Path(builder.build_wheel()).resolve()
            wheel = process_wheel(
                wheel.parent,
                version.value,
                str(target.api),
                abi.value,
                wheel.parent / "tagged",
            )
            normalize_extensions(wheel)
            ndk = Path(os.environ["ANDROID_NDK"])
            libraries = (
                ndk
                / "toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib"
                / abi.triplet
            )
            repair(
                str(wheel),
                str(workspace / "output"),
                os.pathsep.join(
                    [str(Path(builder.host_env) / "chaquopy/lib"), str(libraries)]
                ),
            )


if __name__ == "__main__":
    main()
