"""Build pre-3.13 Android wheels with Chaquopy's PEP 517 build tool."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from build.util import project_wheel_metadata

from scripts.build.android_python import (
    PYTHON_ARCHIVES,
    AndroidABI,
    ChaquopyArchive,
    PyO3ConfigRuntime,
    PythonVersion,
    download_archive,
    setup_python_cross_build,
)


def main() -> None:
    version = PythonVersion(os.environ["TARGET_PYTHON_VERSION"])
    abi = AndroidABI(os.environ["TARGET_ABI"])
    source = PYTHON_ARCHIVES[version]
    if not isinstance(source, ChaquopyArchive):
        raise TypeError(f"Python {version} 应使用现代 Android 构建流程")

    workspace = Path.cwd()
    chaquopy = workspace / "chaquopy"
    package_dir = os.environ["PROJECT_DIR"]
    project = workspace / "library-source" / package_dir
    pypi_dir = chaquopy / "server" / "pypi"
    target_dir = (
        chaquopy / "maven" / "com" / "chaquo" / "python" / "target" / source.release
    )
    download_archive(source.url(abi), target_dir)

    # Chaquopy 的构建器按目标版本查找 pythonX.Y，驱动脚本使用自身虚拟环境。
    host_python = Path(os.environ["HOST_PYTHON"])
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(
        [str(Path(sys.executable).parent), str(host_python.parent), env["PATH"]]
    )

    # 元数据遵循项目本身的构建后端，不能从 Git 标签猜测包版本。
    metadata = project_wheel_metadata(str(project), isolated=True)
    recipe = {
        "package": {"name": metadata["Name"], "version": metadata["Version"]},
        "source": {"path": str(project)},
        "requirements": {"host": ["python"], "build": []},
        "build": {"script_env": []},
    }
    if (project / "Cargo.toml").is_file():
        runtime = setup_python_cross_build(
            Path(os.environ["RUNNER_TEMP"]), version, abi.triplet
        )
        match runtime:
            case PyO3ConfigRuntime(config_file=config_file):
                recipe["requirements"]["build"].append("rust")
                recipe["build"]["script_env"].append(f"PYO3_CONFIG_FILE={config_file}")
            case _:
                raise TypeError("旧版 Chaquopy 构建需要显式 PyO3 配置")

    # compiler-wrapper 只允许 Chaquopy server 目录内的头文件及库路径。
    with tempfile.TemporaryDirectory(
        prefix="android-wheel-recipe-", dir=pypi_dir
    ) as recipe_dir:
        (Path(recipe_dir) / "meta.yaml").write_text(
            yaml.safe_dump(recipe), encoding="utf-8"
        )
        subprocess.run(
            [
                sys.executable,
                str(pypi_dir / "build-wheel.py"),
                "--python",
                version.value,
                "--abi",
                abi.value,
                "--api-level",
                os.environ["ANDROID_API"],
                recipe_dir,
            ],
            env=env,
            check=True,
        )

    distribution = re.sub(r"[-_.]+", "-", metadata["Name"]).lower()
    python_tag = f"cp{version.value.replace('.', '')}"
    platform_tag = f"android_{os.environ['ANDROID_API']}_{abi.value.replace('-', '_')}"
    wheels = list(
        (pypi_dir / "dist" / distribution).glob(
            f"*-{python_tag}-{python_tag}-{platform_tag}.whl"
        )
    )
    if len(wheels) != 1:
        raise ValueError(f"预期只生成一个 wheel，实际找到：{wheels}")
    output_dir = workspace / "output"
    output_dir.mkdir(exist_ok=True)
    shutil.copy2(wheels[0], output_dir / wheels[0].name)


if __name__ == "__main__":
    main()
