"""Verify source-bound license attachment preserves binaries and RECORD."""

import hashlib
import io
import json
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import tomli_w

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.build.wheel_licenses import (
    attach_bundled_licenses,
    license_payload,
    verify_bundled_licenses,
)
from scripts.pipeline.model import SdistSource, Target
from scripts.pipeline.wheel import verify_record
from scripts.recipes.model import Backend
from scripts.testing.wheels import write_wheel


class BundledLicenseTests(unittest.TestCase):
    def test_attach_verified_license_preserves_binary_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = b"Upstream license\n"
            archive = root / "source.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                info = tarfile.TarInfo("source/LICENSE")
                info.size = len(content)
                stream.addfile(info, io.BytesIO(content))
            sha = hashlib.sha256(archive.read_bytes()).hexdigest()
            rule = {
                "sdist-sha256": sha,
                "sources": [
                    {
                        "name": "example",
                        "url": "https://example.test/source.tar.gz",
                        "sha256": sha,
                        "filename": archive.name,
                        "files": [
                            {
                                "path": "LICENSE",
                                "sha256": hashlib.sha256(content).hexdigest(),
                            }
                        ],
                    }
                ],
            }
            registry = root / "licenses.toml"
            registry.write_text(tomli_w.dumps({"example": rule}))
            target = Target(
                "example",
                SdistSource(
                    "example",
                    "1.0",
                    rule["sources"][0]["url"],
                    sha,
                    archive.name,
                    ".",
                    Backend.MESON,
                ),
                PythonVersion.PY313,
                AndroidABI.ARM64,
                24,
            )
            wheel = root / "example-1.0-cp313-cp313-android_24_arm64_v8a.whl"
            prefix = "example-1.0.dist-info/"
            write_wheel(
                wheel,
                {
                    "example.so": b"unchanged binary",
                    prefix + "METADATA": b"Name: example\nVersion: 1.0\n",
                    prefix
                    + "WHEEL": b"Wheel-Version: 1.0\nTag: cp313-cp313-android_24_arm64_v8a\n",
                },
            )
            license_payload.cache_clear()
            self.addCleanup(license_payload.cache_clear)
            with (
                patch("scripts.build.wheel_licenses.REGISTRY", registry),
                patch(
                    "scripts.build.wheel_licenses.download", return_value=archive
                ) as fetch,
            ):
                attach_bundled_licenses(wheel, target)
                first = wheel.read_bytes()
                attach_bundled_licenses(wheel, target)
                self.assertEqual(first, wheel.read_bytes())
                self.assertEqual(fetch.call_count, 1)
                with zipfile.ZipFile(wheel) as output:
                    self.assertEqual(output.read("example.so"), b"unchanged binary")
                    self.assertEqual(
                        json.loads(output.read(prefix + "bundled-libraries.json")), rule
                    )
                    verify_record(output, prefix + "RECORD")
                    verify_bundled_licenses(output, target, prefix)
                altered = io.BytesIO()
                with zipfile.ZipFile(altered, "w") as output:
                    output.writestr(prefix + "bundled-libraries.json", "{}")
                with (
                    zipfile.ZipFile(altered) as output,
                    self.assertRaisesRegex(ValueError, "来源记录不一致"),
                ):
                    verify_bundled_licenses(output, target, prefix)
