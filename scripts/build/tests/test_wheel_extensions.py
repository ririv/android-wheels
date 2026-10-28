"""Check extension path normalization preserves code, metadata and RECORD."""

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build.wheel_extensions import normalize_extensions
from scripts.pipeline.wheel import verify_record
from scripts.testing.wheels import write_wheel


class WheelExtensionTests(unittest.TestCase):
    def test_host_suffix_becomes_portable_without_changing_elf_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "example-1.0-cp311-cp311-android_24_arm64_v8a.whl"
            prefix = "example-1.0.dist-info/"
            binary = b"\x7fELFcross-compiled-code"
            write_wheel(
                path,
                {
                    "example/_core.cpython-311-x86_64-linux-gnu.so": binary,
                    prefix + "METADATA": b"Name: example\nVersion: 1.0\n",
                    prefix
                    + "WHEEL": b"Wheel-Version: 1.0\nTag: cp311-cp311-android_24_arm64_v8a\n",
                },
            )
            normalize_extensions(path)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(archive.read("example/_core.so"), binary)
                self.assertNotIn(
                    "example/_core.cpython-311-x86_64-linux-gnu.so", archive.namelist()
                )
                verify_record(archive, prefix + "RECORD")
