"""Verify native SDK reuse preserves target identity and filesystem contents."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.build.native_cache import cache_key, seal, verify
from scripts.build.native_model import NativeLibrary
from scripts.pipeline.model import GitSource, Target
from scripts.recipes.model import Backend


class NativeCacheTests(unittest.TestCase):
    def test_python_independent_identity_changes_with_android_target(self):
        target = Target(
            "example",
            GitSource("owner/repo", "main", "a" * 40, ".", Backend.SETUPTOOLS),
            PythonVersion.PY313,
            AndroidABI.ARM64,
            26,
            native_dependencies=(NativeLibrary.ARROW,),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.properties").write_text("Pkg.Revision = 27.3.13750724\n")
            key = cache_key(target, root / "prefix", root)
            self.assertEqual(
                key,
                cache_key(
                    replace(target, python=PythonVersion.PY315), root / "prefix", root
                ),
            )
            self.assertNotEqual(
                key,
                cache_key(
                    replace(target, abi=AndroidABI.X86_64), root / "prefix", root
                ),
            )
            self.assertNotEqual(
                key, cache_key(replace(target, api=28), root / "prefix", root)
            )

    def test_sdk_roundtrip_checks_payload_permissions_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "native-libraries.json").write_text("[]")
            library = root / "libexample.so.1"
            library.write_bytes(b"original SDK")
            (root / "libexample.so").symlink_to(library.name)
            seal(root, "identity")
            verify(root, "identity")
            library.write_bytes(b"tampered SDK")
            with self.assertRaisesRegex(ValueError, "文件校验失败"):
                verify(root, "identity")
            library.write_bytes(b"original SDK")
            library.chmod(0o700)
            with self.assertRaises(ValueError):
                verify(root, "identity")
