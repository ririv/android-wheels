"""Verify transitive Android runtime dependencies and artifact boundaries."""

import tempfile
import unittest
from pathlib import Path

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.pipeline.artifacts import digest
from scripts.pipeline.model import GitSource, Plan, Target
from scripts.recipes.model import Backend, Publication
from scripts.testing.runtime_dependencies import (
    native_dependency,
    pure_dependency,
    verify_closure,
)
from scripts.testing.wheels import write_wheel

TARGET = Target(
    "example",
    GitSource("owner/repo", "main", "a" * 40, ".", Backend.SETUPTOOLS),
    PythonVersion.PY313,
    AndroidABI.ARM64,
    24,
)


def wheel(root: Path, name: str, requires: str = "") -> Path:
    path = root / f"{name}-1.0-py3-none-any.whl"
    prefix = f"{name}-1.0.dist-info/"
    write_wheel(
        path,
        {
            name + ".py": b"",
            prefix + "METADATA": (f"Name: {name}\nVersion: 1.0\n" + requires).encode(),
            prefix + "WHEEL": b"Wheel-Version: 1.0\nTag: py3-none-any\n",
        },
    )
    return path


class RuntimeDependencyTests(unittest.TestCase):
    def test_complete_transitive_dependency_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = wheel(root, "example", "Requires-Dist: helper>=1\n")
            helper = wheel(root, "helper")
            self.assertEqual(pure_dependency(helper, digest(helper), TARGET), helper)
            report = verify_closure((first, helper), TARGET)
            self.assertEqual([row["package"] for row in report], ["example", "helper"])
            with self.assertRaisesRegex(ValueError, "运行依赖不满足"):
                verify_closure((first,), TARGET)

    def test_markers_use_android_instead_of_build_host(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = wheel(
                Path(temporary),
                "example",
                'Requires-Dist: android_helper; sys_platform == "android"\nRequires-Dist: windows_helper; sys_platform == "win32"\nRequires-Dist: optional_helper; extra == "test"\n',
            )
            with self.assertRaisesRegex(ValueError, "android_helper"):
                verify_closure((first,), TARGET)
            helper = wheel(Path(temporary), "android_helper")
            self.assertEqual(len(verify_closure((first, helper), TARGET)), 2)

    def test_pure_wheel_hash_is_checked_before_installation(self):
        with tempfile.TemporaryDirectory() as temporary:
            dependency = wheel(Path(temporary), "helper")
            with self.assertRaisesRegex(ValueError, "哈希不一致"):
                pure_dependency(dependency, "0" * 64, TARGET)

    def test_native_dependency_cannot_cross_device_abis(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dependency = Target(
                "helper", TARGET.source, TARGET.python, AndroidABI.X86_64, 24
            )
            Plan(Publication.BUILD, (dependency,)).write(root / "plan.json")
            with self.assertRaisesRegex(ValueError, "与目标不一致"):
                native_dependency(
                    root / "plan.json", root / dependency.artifact, TARGET
                )
