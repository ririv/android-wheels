"""Verify historical timestamps and index generation without wheel checkouts."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.index.metadata import read_wheels
from scripts.index.render import render


class IndexTests(unittest.TestCase):
    def test_git_metadata_survives_sparse_checkout_and_preserves_historical_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def git(*args):
                return subprocess.check_output(
                    [
                        "git",
                        "-c",
                        "user.name=Test",
                        "-c",
                        "user.email=test@example.invalid",
                        *args,
                    ],
                    cwd=root,
                    text=True,
                    stderr=subprocess.PIPE,
                )

            git("init", "-b", "wheels")
            (root / "some_pkg").mkdir()
            wheel = root / "some_pkg/some_pkg-1.0-py3-none-any.whl"
            wheel.write_bytes(b"not needed for indexing")
            git("add", ".")
            git("commit", "-m", "initial")
            git("sparse-checkout", "set", "--no-cone", ".index-metadata")
            self.assertFalse(wheel.exists())
            metadata = read_wheels(root)
            self.assertEqual(len(metadata), 1)
            self.assertGreater(metadata[0].modified.year, 2020)
            output = root / "public"
            render(metadata, "ririv/py-extra-wheels", output)
            self.assertIn('href="some-pkg/"', (output / "index.html").read_text())
            self.assertIn(
                "https://github.com/ririv/py-extra-wheels/raw/wheels/some_pkg/some_pkg-1.0-py3-none-any.whl",
                (output / "some-pkg/index.html").read_text(),
            )

    def test_empty_repository_is_not_published_as_an_empty_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(
                ["git", "init", "-b", "wheels"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "--allow-empty",
                    "-m",
                    "initial",
                ],
                cwd=root,
                check=True,
                capture_output=True,
            )
            with self.assertRaisesRegex(ValueError, "空索引"):
                read_wheels(root)
