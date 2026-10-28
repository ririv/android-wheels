"""Reject inconsistent wheel metadata and tampered RECORD contents."""

import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.pipeline.model import GitSource, SdistSource, Target
from scripts.pipeline.wheel import verify_wheel
from scripts.recipes.model import Backend
from scripts.testing.wheels import write_wheel

TARGET = Target(
    "example",
    GitSource("owner/repo", "main", "a" * 40, ".", Backend.MATURIN),
    PythonVersion.PY313,
    AndroidABI.ARM64,
    24,
)
PREFIX = "example-1.0.dist-info/"


class WheelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = (
            Path(temporary.name) / "example-1.0-cp313-cp313-android_24_arm64_v8a.whl"
        )
        self.files = {
            PREFIX + "METADATA": b"Name: example\nVersion: 1.0\n",
            PREFIX
            + "WHEEL": b"Wheel-Version: 1.0\nTag: cp313-cp313-android_24_arm64_v8a\n",
            "example/__init__.py": b"value = 1\n",
        }

    def test_valid_complete_wheel(self):
        write_wheel(self.path, self.files)
        verify_wheel(self.path, TARGET)

    def test_sdist_wheel_must_match_the_pinned_release_version(self):
        write_wheel(self.path, self.files)
        source = SdistSource(
            "example",
            "2.0",
            "https://example/source.tar.gz",
            "a" * 64,
            "source.tar.gz",
            ".",
            Backend.MATURIN,
        )
        with self.assertRaisesRegex(ValueError, "PyPI 发行版本"):
            verify_wheel(self.path, replace(TARGET, source=source))

    def test_internal_platform_must_match_filename(self):
        self.files[PREFIX + "WHEEL"] = (
            b"Wheel-Version: 1.0\nTag: cp313-cp313-linux_x86_64\n"
        )
        write_wheel(self.path, self.files)
        with self.assertRaisesRegex(ValueError, "标签"):
            verify_wheel(self.path, TARGET)

    def test_missing_wheel_and_record_are_rejected(self):
        with zipfile.ZipFile(self.path, "w") as archive:
            archive.writestr(PREFIX + "METADATA", self.files[PREFIX + "METADATA"])
        with self.assertRaisesRegex(ValueError, "WHEEL 和 RECORD"):
            verify_wheel(self.path, TARGET)

    def test_record_hash_and_file_set_are_verified(self):
        write_wheel(self.path, self.files)
        with zipfile.ZipFile(self.path) as archive:
            files = {info.filename: archive.read(info) for info in archive.infolist()}
        files["example/__init__.py"] = b"value = 2\n"
        with zipfile.ZipFile(self.path, "w") as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        with self.assertRaisesRegex(ValueError, "RECORD 哈希"):
            verify_wheel(self.path, TARGET)
        files["extra.py"] = b"unrecorded"
        with zipfile.ZipFile(self.path, "w") as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        with self.assertRaisesRegex(ValueError, "文件集合"):
            verify_wheel(self.path, TARGET)
