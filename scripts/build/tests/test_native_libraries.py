"""Verify native dependency provenance survives packaging and publication checks."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.build.native_libraries import library_specs
from scripts.build.native_model import NativeLibrary
from scripts.build.tests.test_wheel_abi import elf_with_dependency
from scripts.build.wheel_native import attach_native_metadata
from scripts.pipeline.artifacts import collect, record
from scripts.pipeline.model import GitSource, Plan, Target, load_plan
from scripts.recipes.model import Backend, Publication
from scripts.testing.wheels import write_wheel


class NativeLibraryTests(unittest.TestCase):
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
