"""Verify runtime selection, cache boundaries, and cross-compilation configuration."""

import io
import os
import tarfile
import tempfile
import tomllib
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.build.android_python import (
    PYTHON_ARCHIVES,
    AndroidABI,
    ChaquopyArchive,
    CPythonArchive,
    PyO3ConfigRuntime,
    PythonVersion,
    SysconfigRuntime,
    download_archive,
    setup_python_cross_build,
)
from scripts.build.build_android_wheel import (
    create_cargo_config,
    prepare_build_environment,
    process_wheel,
)


class AndroidPythonTests(unittest.TestCase):
    def test_supported_runtimes_and_cache_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archives = {}
            for version in PythonVersion:
                for abi in AndroidABI:
                    source = PYTHON_ARCHIVES[version]
                    url = source.url(abi)
                    archive = root / url.rsplit("/", 1)[1]
                    lib = f"libpython{version.value}.so"
                    match source:
                        case ChaquopyArchive():
                            with zipfile.ZipFile(archive, "w") as zf:
                                zf.writestr(f"jniLibs/{abi.value}/{lib}", b"\x7fELF")
                        case CPythonArchive():
                            with tarfile.open(archive, "w:gz") as tf:
                                for name, data in {
                                    f"prefix/lib/{lib}": b"\x7fELF",
                                    f"prefix/lib/python{version}/_sysconfigdata_android.py": b"build_time_vars = {}",
                                }.items():
                                    info = tarfile.TarInfo(name)
                                    info.size = len(data)
                                    tf.addfile(info, io.BytesIO(data))
                    archives[url] = archive

            locations = set()
            with patch(
                "scripts.build.android_python.download_archive",
                side_effect=lambda url, _: archives[url],
            ):
                for version in PythonVersion:
                    for abi in AndroidABI:
                        with self.subTest(version=version, abi=abi):
                            runtime = setup_python_cross_build(
                                root, version, abi.triplet
                            )
                            self.assertEqual(
                                (
                                    runtime.lib_dir / f"libpython{version}.so"
                                ).read_bytes(),
                                b"\x7fELF",
                            )
                            self.assertNotIn(runtime.lib_dir, locations)
                            locations.add(runtime.lib_dir)
                            match runtime:
                                case PyO3ConfigRuntime(config_file=config):
                                    content = dict(
                                        line.split("=", 1)
                                        for line in config.read_text().splitlines()
                                    )
                                    self.assertEqual(content["version"], version.value)
                                    self.assertEqual(
                                        content["ext_suffix"],
                                        f".cpython-{version.value.replace('.', '')}.so",
                                    )
                                    self.assertEqual(
                                        content["lib_dir"], str(runtime.lib_dir)
                                    )
                                case SysconfigRuntime():
                                    self.assertTrue(
                                        list(
                                            runtime.lib_dir.rglob("_sysconfigdata*.py")
                                        )
                                    )
                            # 第二次调用必须重用相同版本与 ABI 的解包结果。
                            marker = runtime.lib_dir / "cache-marker"
                            marker.touch()
                            cached = setup_python_cross_build(
                                root, version, abi.triplet
                            )
                            self.assertEqual(cached, runtime)
                            self.assertTrue(marker.is_file())

    def test_failed_download_does_not_select_another_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            url = PYTHON_ARCHIVES[PythonVersion.PY311].url(AndroidABI.ARM64)
            error = urllib.error.HTTPError(url, 404, "not found", {}, None)
            with patch(
                "scripts.build.android_python.urllib.request.urlretrieve",
                side_effect=error,
            ) as download:
                with self.assertRaises(urllib.error.HTTPError):
                    setup_python_cross_build(root, "3.11", AndroidABI.ARM64.triplet)
                download.assert_called_once()
            self.assertFalse(list(root.rglob(".complete")))
            self.assertFalse(list(root.rglob("*.part")))

    def test_partial_download_is_removed_and_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def partial_download(url, path):
                path.write_bytes(b"incomplete")
                raise OSError("下载中断")

            with patch(
                "scripts.build.android_python.urllib.request.urlretrieve",
                side_effect=partial_download,
            ):
                with self.assertRaises(OSError):
                    download_archive("https://example.com/python.zip", root)
            self.assertEqual(list(root.iterdir()), [])

    def test_incomplete_extraction_is_rebuilt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = PYTHON_ARCHIVES[PythonVersion.PY311]
            archive = root / source.url(AndroidABI.ARM64).rsplit("/", 1)[1]
            runtime_dir = root / "android-python" / archive.stem
            runtime_dir.mkdir(parents=True)
            (runtime_dir / "incomplete").touch()
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("jniLibs/arm64-v8a/libpython3.11.so", b"\x7fELF")
            with patch(
                "scripts.build.android_python.download_archive", return_value=archive
            ):
                setup_python_cross_build(root, "3.11", AndroidABI.ARM64.triplet)
            self.assertFalse((runtime_dir / "incomplete").exists())
            self.assertTrue((runtime_dir / ".complete").is_file())

    def test_build_environment_preserves_host_and_selects_one_python_config(self):
        runtimes = [
            PyO3ConfigRuntime(Path("/target/lib"), Path("/target/pyo3-config.txt")),
            SysconfigRuntime(Path("/target/lib")),
        ]
        for runtime in runtimes:
            with (
                self.subTest(runtime=runtime),
                patch.dict(
                    os.environ,
                    {
                        "PATH": "/host/bin",
                        "HOME": "/host/home",
                        "HOST_PYTHON": "/host/python/bin/python",
                        "PYO3_CONFIG_FILE": "/stale/config",
                        "PYO3_CROSS_LIB_DIR": "/stale/lib",
                    },
                    clear=True,
                ),
            ):
                env = prepare_build_environment(
                    Path("/ndk"), AndroidABI.ARM64.triplet, "24", "3.11", runtime
                )
                self.assertEqual(env["HOME"], "/host/home")
                self.assertIn("/host/python/bin", env["PATH"].split(os.pathsep))
                self.assertEqual(env["CARGO_BUILD_TARGET"], AndroidABI.ARM64.triplet)
                match runtime:
                    case PyO3ConfigRuntime():
                        self.assertEqual(
                            env["PYO3_CONFIG_FILE"], "/target/pyo3-config.txt"
                        )
                        self.assertNotIn("PYO3_CROSS_LIB_DIR", env)
                    case SysconfigRuntime():
                        self.assertEqual(env["PYO3_CROSS_LIB_DIR"], "/target/lib")
                        self.assertNotIn("PYO3_CONFIG_FILE", env)

    def test_cargo_config_keeps_project_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cargo").mkdir()
            config = root / ".cargo" / "config.toml"
            config.write_text(
                '[build]\njobs=2\n[target.aarch64-linux-android]\nrustflags=["-C", "opt-level=2"]\n'
            )
            create_cargo_config(
                root, AndroidABI.ARM64.triplet, Path("/python/lib"), "/ndk/clang"
            )
            actual = tomllib.loads(config.read_text())
            self.assertEqual(actual["build"]["jobs"], 2)
            self.assertEqual(
                actual["target"][AndroidABI.ARM64.triplet],
                {
                    "linker": "/ndk/clang",
                    "rustflags": ["-C", "opt-level=2", "-L", "/python/lib"],
                },
            )
            create_cargo_config(
                root, AndroidABI.ARM64.triplet, Path("/python/lib"), "/ndk/clang"
            )
            self.assertEqual(tomllib.loads(config.read_text()), actual)


class WheelTagsTests(unittest.TestCase):
    def test_android_tag_updates_metadata_and_preserves_abi3(self):
        from wheel.wheelfile import WheelFile

        for python_tag, abi_tag in [("cp311", "cp311"), ("cp310", "abi3")]:
            with (
                self.subTest(python_tag=python_tag, abi_tag=abi_tag),
                tempfile.TemporaryDirectory() as tmp,
            ):
                root = Path(tmp)
                wheel_dir = root / "wheelhouse"
                wheel_dir.mkdir()
                filename = f"example-1.0-{python_tag}-{abi_tag}-linux_aarch64.whl"
                info = "example-1.0.dist-info"
                with WheelFile(str(wheel_dir / filename), "w") as wf:
                    wf.writestr(
                        f"{info}/WHEEL",
                        f"Wheel-Version: 1.0\nTag: {python_tag}-{abi_tag}-linux_aarch64\n",
                    )
                    wf.writestr(
                        f"{info}/METADATA",
                        "Metadata-Version: 2.1\nName: example\nVersion: 1.0\n",
                    )
                    wf.writestr("example.so", b"\x7fELF")
                process_wheel(wheel_dir, "3.11", "24", "arm64-v8a", root / "output")
                result = (
                    root
                    / "output"
                    / filename.replace("linux_aarch64", "android_24_arm64_v8a")
                )
                with WheelFile(str(result)) as wf:
                    # WheelFile 校验读取成员的 RECORD 哈希。
                    for member in wf.namelist():
                        wf.read(member)
                    metadata = wf.read(f"{info}/WHEEL").decode()
                    self.assertIn(
                        f"Tag: {python_tag}-{abi_tag}-android_24_arm64_v8a", metadata
                    )
                    self.assertNotIn("linux_aarch64", metadata)


if __name__ == "__main__":
    unittest.main()
