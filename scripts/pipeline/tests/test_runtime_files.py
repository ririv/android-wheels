"""Verify fixture hashes and protect executable runtime files during deployment."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.pipeline.artifacts import digest
from scripts.testing.runtime_files import copy_resources, manifest_resources


class RuntimeFileTests(unittest.TestCase):
    def test_manifest_deploys_verified_files_without_overwriting_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "test-ca.pem"
            source.write_text("public test certificate")
            row = {"filename": source.name, "sha256": digest(source)}
            manifest = root / "resources.json"
            manifest.write_text(json.dumps([row]))
            destination = root / "runtime"
            destination.mkdir()
            resources = manifest_resources(manifest)
            self.assertEqual(copy_resources(resources, destination), [row])
            self.assertEqual(
                (destination / source.name).read_bytes(), source.read_bytes()
            )
            with self.assertRaises(FileExistsError):
                copy_resources(resources, destination)
            source.write_text("tampered certificate")
            with self.assertRaisesRegex(ValueError, "哈希校验失败"):
                copy_resources(resources, destination)

    def test_manifest_cannot_escape_fixture_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "resources.json"
            manifest.write_text(
                json.dumps([{"filename": "../private.key", "sha256": "a" * 64}])
            )
            with self.assertRaises(ValueError):
                manifest_resources(manifest)
