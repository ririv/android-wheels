"""Verify a shared SDK composes with an existing target Python prefix."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build.native_libraries import library_specs
from scripts.build.native_model import NativeLibrary
from scripts.build.native_prefix import install_libraries
from scripts.build.pg_config import write_pg_config


class NativePrefixTests(unittest.TestCase):
    def test_sdk_install_preserves_python_files_and_relocatable_host_tools(self):
        specs = library_specs(
            Path(__file__).resolve().parents[1] / "native-libraries.toml"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "sdk"
            source.mkdir()
            (source / "lib").mkdir()
            (source / "lib/libpq.so").write_bytes(b"verified target payload")
            (source / "native-libraries.json").write_text(
                json.dumps([specs[NativeLibrary.LIBPQ].to_dict()])
            )
            write_pg_config(source, specs[NativeLibrary.LIBPQ].version)
            destination = root / "python-prefix"
            destination.mkdir()
            (destination / "Python.h").write_text("existing target header")
            install_libraries(source, destination, (NativeLibrary.LIBPQ,))
            self.assertEqual(
                (destination / "Python.h").read_text(), "existing target header"
            )
            self.assertEqual(
                (destination / "lib/libpq.so").read_bytes(), b"verified target payload"
            )
            self.assertTrue(
                (destination / "host-tools/bin/pg_config").stat().st_mode & 0o100
            )
