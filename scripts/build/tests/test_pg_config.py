"""Verify the host query tool follows a relocated target prefix."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.build.pg_config import write_pg_config


class PgConfigTests(unittest.TestCase):
    def test_host_queries_follow_the_relocated_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = root / "native"
            write_pg_config(original, "18.6")
            moved = (root / "prefix with spaces").resolve()
            shutil.move(original, moved)
            binary = moved / "host-tools/bin/pg_config"
            expected = {
                "--version": "PostgreSQL 18.6",
                "--libdir": str(moved / "lib"),
                "--includedir": str(moved / "include"),
                "--includedir-server": str(moved / "include/postgresql/server"),
                "--cppflags": "-I" + str(moved / "include"),
                "--ldflags": "-L" + str(moved / "lib"),
            }
            for query, value in expected.items():
                with self.subTest(query=query):
                    self.assertEqual(
                        subprocess.check_output(
                            [str(binary), query], text=True
                        ).strip(),
                        value,
                    )
