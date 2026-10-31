"""Verify native dependency provenance survives packaging and publication checks."""

import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.build.native_libraries import commands, library_specs
from scripts.build.native_model import NativeLibrary
from scripts.build.tests.test_wheel_abi import elf_with_dependency
from scripts.build.wheel_native import attach_native_metadata
from scripts.pipeline.artifacts import collect, record
from scripts.pipeline.model import GitSource, Plan, Target, load_plan
from scripts.recipes.model import Backend, Publication
from scripts.testing.wheels import write_wheel


class NativeLibraryTests(unittest.TestCase):
    def test_arrow_uses_cpp_root_and_postgresql_builds_only_the_client(self):
        root = Path(__file__).resolve().parents[3]
        specs = library_specs(root / "scripts/build/native-libraries.toml")
        arguments = (
            Path("/source"),
            Path("/build"),
            Path("/prefix"),
            Path("/ndk"),
            AndroidABI.ARM64,
            26,
        )
        arrow = commands(specs[NativeLibrary.ARROW], *arguments)
        self.assertEqual(arrow[0][arrow[0].index("-S") + 1], "/source/cpp")
        client = commands(specs[NativeLibrary.LIBPQ], *arguments)
        self.assertEqual(client[1], ["make", "-j2", "-C", "src/interfaces/libpq"])
        self.assertEqual(client[2], ["make", "-C", "src/interfaces/libpq", "install"])
        self.assertEqual(client[3], ["make", "-C", "src/include", "install"])
        self.assertEqual(
            specs[NativeLibrary.ARROW].to_dict()["source-directory"], "cpp"
        )
        self.assertNotIn("source-directory", specs[NativeLibrary.OPENSSL].to_dict())

    def test_openblas_cross_targets_keep_lp64_and_c_lapack(self):
        root = Path(__file__).resolve().parents[3]
        specs = library_specs(root / "scripts/build/native-libraries.toml")
        library = specs[NativeLibrary.OPENBLAS]
        for abi, cpu in ((AndroidABI.ARM64, "ARMV8"), (AndroidABI.X86_64, "NEHALEM")):
            with self.subTest(abi=abi):
                configure, build, install = commands(
                    library,
                    Path("/source"),
                    Path("/build"),
                    Path("/prefix"),
                    Path("/ndk"),
                    abi,
                    24,
                )
                self.assertIn(f"-DANDROID_ABI={abi}", configure)
                self.assertIn(f"-DTARGET={cpu}", configure)
                self.assertIn("-DNOFORTRAN=ON", configure)
                self.assertIn("-DC_LAPACK=ON", configure)
                self.assertIn("-DBUILD_WITHOUT_LAPACK=OFF", configure)
                self.assertIn("-DINTERFACE64=OFF", configure)
                self.assertEqual(
                    build, ["cmake", "--build", "/build", "--parallel", "2"]
                )
                self.assertEqual(install, ["cmake", "--install", "/build"])
        self.assertEqual(
            library.to_dict()["abi-args"],
            {"arm64-v8a": ["-DTARGET=ARMV8"], "x86_64": ["-DTARGET=NEHALEM"]},
        )
        self.assertNotIn("abi-args", specs[NativeLibrary.LIBFFI].to_dict())

    def test_pinned_native_source_and_license_survive_the_artifact_roundtrip(self):
        root = Path(__file__).resolve().parents[3]
        spec = library_specs(root / "scripts/build/native-libraries.toml")[
            NativeLibrary.LIBFFI
        ]
        target = Target(
            "example",
            GitSource("owner/repo", "main", "a" * 40, ".", Backend.SETUPTOOLS),
            PythonVersion.PY313,
            AndroidABI.ARM64,
            24,
            native_dependencies=(NativeLibrary.LIBFFI,),
        )
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            prefix = directory / "native"
            license_path = prefix / "licenses/libffi/LICENSE"
            license_path.parent.mkdir(parents=True)
            license_path.write_text("upstream license")
            (prefix / "native-libraries.json").write_text(json.dumps([spec.to_dict()]))
            folder = directory / "artifacts" / target.artifact
            folder.mkdir(parents=True)
            wheel = folder / "example-1.0-cp313-cp313-android_24_arm64_v8a.whl"
            info = "example-1.0.dist-info/"
            write_wheel(
                wheel,
                {
                    "example.so": elf_with_dependency("libpython3.13.so"),
                    info + "METADATA": b"Name: example\nVersion: 1.0\n",
                    info
                    + "WHEEL": b"Wheel-Version: 1.0\nTag: cp313-cp313-android_24_arm64_v8a\n",
                },
            )
            # auditwheel 产物会包含显式目录项；它们不属于 RECORD 文件集合。
            with zipfile.ZipFile(wheel, "a") as archive:
                archive.writestr("example-1.0.dist-info/licenses/", b"")
            with patch.dict(
                os.environ,
                {"NATIVE_DEPENDENCIES": "libffi", "NATIVE_PREFIX": str(prefix)},
            ):
                attach_native_metadata(wheel)
            record(folder, target)
            plan = Plan(Publication.BUILD, (target,))
            plan.write(directory / "plan.json")
            loaded = load_plan(directory / "plan.json")
            self.assertEqual(loaded, plan)
            self.assertEqual(
                list(collect(directory / "artifacts", loaded).values()), [wheel]
            )
