"""Check Android compatibility tags against real ELF dynamic dependencies."""

import struct
import tempfile
import unittest
from pathlib import Path

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.build.wheel_abi import constrain_abi, python_versions
from scripts.pipeline.model import GitSource, Target
from scripts.pipeline.wheel import verify_wheel
from scripts.recipes.model import Backend
from scripts.testing.wheels import write_wheel


def elf_with_dependency(name: str) -> bytes:
    names = b"\0.shstrtab\0.dynstr\0.dynamic\0"
    strings = b"\0" + name.encode() + b"\0"
    offset = 64 + 4 * 64
    dynamic_offset = offset + len(names) + len(strings)
    header = struct.pack(
        "<16sHHIQQQIHHHHHH",
        b"\x7fELF\x02\x01\x01" + b"\0" * 9,
        3,
        183,
        1,
        0,
        0,
        64,
        0,
        64,
        0,
        0,
        64,
        4,
        1,
    )
    sections = b"\0" * 64
    for fields in (
        (1, 3, 0, 0, offset, len(names), 0, 0, 1, 0),
        (11, 3, 0, 0, offset + len(names), len(strings), 0, 0, 1, 0),
        (19, 6, 0, 0, dynamic_offset, 32, 2, 0, 8, 16),
    ):
        sections += struct.pack("<IIQQQQIIQQ", *fields)
    return header + sections + names + strings + struct.pack("<QQQQ", 1, 1, 0, 0)


class WheelABITests(unittest.TestCase):
    def make_wheel(self, root: Path, dependency: str, python="cp310", abi="abi3"):
        path = root / f"example-1.0-{python}-{abi}-android_24_arm64_v8a.whl"
        prefix = "example-1.0.dist-info/"
        write_wheel(
            path,
            {
                "example.abi3.so": elf_with_dependency(dependency),
                prefix + "METADATA": b"Name: example\nVersion: 1.0\n",
                prefix
                + "WHEEL": f"Wheel-Version: 1.0\nTag: {python}-{abi}-android_24_arm64_v8a\n".encode(),
            },
        )
        return path

    def test_versioned_python_dependency_narrows_tags_and_rewrites_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = self.make_wheel(Path(tmp), "libpython3.13.so")
            self.assertEqual(python_versions(original), {"3.13"})
            result = constrain_abi(original)
            self.assertEqual(
                result.name, "example-1.0-cp313-cp313-android_24_arm64_v8a.whl"
            )
            self.assertFalse(original.exists())
            target = Target(
                "example",
                GitSource("owner/repo", "main", "a" * 40, ".", Backend.SETUPTOOLS),
                PythonVersion.PY313,
                AndroidABI.ARM64,
                24,
            )
            verify_wheel(result, target)

    def test_unversioned_python_dependency_preserves_upstream_abi3(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = self.make_wheel(Path(tmp), "libpython3.so")
            self.assertEqual(constrain_abi(wheel), wheel)

    def test_version_specific_wheel_must_match_its_linked_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = self.make_wheel(Path(tmp), "libpython3.13.so", "cp314", "cp314")
            with self.assertRaisesRegex(ValueError, "不一致"):
                constrain_abi(wheel)
