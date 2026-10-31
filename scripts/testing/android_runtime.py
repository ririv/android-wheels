"""Run a verified wheel on an explicitly selected Android device and runtime."""

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.build.android_python import (
    PYTHON_ARCHIVES,
    AndroidABI,
    PythonVersion,
    SysconfigRuntime,
    setup_python_cross_build,
)
from scripts.build.link_flags import PAGE_LINK_FLAGS
from scripts.pipeline.artifacts import digest
from scripts.pipeline.model import load_plan
from scripts.pipeline.wheel import verify_wheel
from scripts.testing.runtime_dependencies import (
    native_dependency,
    pure_dependency,
    verify_closure,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--dependency",
        nargs=2,
        action="append",
        default=[],
        metavar=("PLAN", "ARTIFACT"),
    )
    parser.add_argument(
        "--pure-dependency",
        nargs=2,
        action="append",
        default=[],
        metavar=("WHEEL", "SHA256"),
    )
    args = parser.parse_args()
    plan = load_plan(args.plan)
    target = plan.target(args.artifact.name)
    if target.python not in {
        PythonVersion.PY313,
        PythonVersion.PY314,
        PythonVersion.PY315,
    }:
        raise ValueError("运行检查需要包含完整标准库的 CPython 3.13–3.15 归档")
    manifest = json.loads((args.artifact / "manifest.json").read_text())
    if manifest["target"] != target.to_dict():
        raise ValueError("运行产物与构建计划不一致")
    filename = manifest["wheel"]
    if Path(filename).name != filename:
        raise ValueError("无效的 wheel 文件名")
    wheel = args.artifact / filename
    if digest(wheel) != manifest["sha256"]:
        raise ValueError("运行产物哈希不一致")
    verify_wheel(wheel, target)
    wheels = (
        wheel,
        *(
            native_dependency(Path(plan), Path(artifact), target)
            for plan, artifact in args.dependency
        ),
        *(
            pure_dependency(Path(path), sha256, target)
            for path, sha256 in args.pure_dependency
        ),
    )
    inventory = verify_closure(wheels, target)
    adb = [str(args.adb), "-s", args.serial]

    def shell(*command: str) -> str:
        return subprocess.check_output(
            [*adb, "shell", shlex.join(command)], text=True, timeout=180
        ).strip()

    device_abi = shell("getprop", "ro.product.cpu.abi")
    if AndroidABI(device_abi) != target.abi:
        raise ValueError("设备 ABI 与 wheel 不一致")
    with tempfile.TemporaryDirectory(prefix="android-wheel-runtime-") as temporary:
        root = Path(temporary)
        runtime = setup_python_cross_build(root, target.python, target.abi.triplet)
        if not isinstance(runtime, SysconfigRuntime):
            raise TypeError("运行检查需要完整 CPython 归档")
        prefix = root / "deployment/prefix"
        # adb 的同步协议不能可靠创建归档中的符号链接，部署时复制其目标内容。
        shutil.copytree(runtime.lib_dir.parent, prefix)
        launcher = root / "main.c"
        launcher.write_text(
            "#include <Python.h>\n"
            "int main(int argc, char **argv) { return Py_BytesMain(argc, argv); }\n"
        )
        executable = prefix / "bin/python"
        executable.parent.mkdir()
        subprocess.run(
            [
                str(args.toolchain / "bin" / f"{target.abi.triplet}{target.api}-clang"),
                str(launcher),
                f"-I{prefix}/include/python{target.python}",
                f"-L{runtime.lib_dir}",
                f"-lpython{target.python}",
                *PAGE_LINK_FLAGS,
                "-o",
                str(executable),
            ],
            check=True,
        )
        site = prefix / "lib" / f"python{target.python}" / "site-packages"
        site.mkdir(exist_ok=True)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--no-compile",
                "--only-binary=:all:",
                *(
                    argument
                    for api in range(target.api, 20, -1)
                    for argument in (
                        "--platform",
                        f"android_{api}_{target.abi.value.replace('-', '_')}",
                    )
                ),
                "--python-version",
                target.python.value,
                "--implementation",
                "cp",
                "--abi",
                f"cp{target.python.value.replace('.', '')}",
                "--target",
                str(site),
                *(str(path) for path in wheels),
            ],
            check=True,
        )
        shutil.copy2(args.script, prefix / "runtime-test.py")
        remote = "/data/local/tmp/" + root.name
        shell("mkdir", remote)
        try:
            subprocess.run([*adb, "push", str(prefix), remote], check=True, timeout=180)
            device_prefix = remote + "/prefix"
            shell("chmod", "755", device_prefix + "/bin/python")
            output = shell(
                "env",
                "PYTHONHOME=" + device_prefix,
                "LD_LIBRARY_PATH=" + device_prefix + "/lib",
                "OPENBLAS_NUM_THREADS=2",
                "OMP_NUM_THREADS=2",
                device_prefix + "/bin/python",
                "-u",
                device_prefix + "/runtime-test.py",
            )
            report = {
                "target": target.to_dict(),
                "device": {
                    "abi": device_abi,
                    "api": int(shell("getprop", "ro.build.version.sdk")),
                    "fingerprint": shell("getprop", "ro.build.fingerprint"),
                },
                "wheel": filename,
                "sha256": manifest["sha256"],
                "installed_wheels": inventory,
                "script_sha256": digest(args.script),
                "runtime_archive": {
                    "url": PYTHON_ARCHIVES[target.python].url(target.abi),
                    "sha256": digest(
                        next((root / "android-python/archives").iterdir())
                    ),
                },
                "runtime": json.loads(output),
            }
            args.report.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2), flush=True)
        finally:
            shell("rm", "-rf", remote)


if __name__ == "__main__":
    main()
