"""Exercise explicit sdist sources, hash verification and release metadata."""

import hashlib
import io
import json
import tarfile
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.pipeline.model import Plan, SdistSource, Target, load_plan
from scripts.pipeline.sdists import download
from scripts.pipeline.source import prepare_sdist, resolve_source
from scripts.recipes.load import load_recipe
from scripts.recipes.model import Backend, Publication, PyPILocation
from scripts.recipes.request import requested_builds


class SdistTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.archive = self.root / "example-1.2.3.tar.gz"
        self.files = {
            "pyproject.toml": b'[build-system]\nbuild-backend="setuptools.build_meta"\n',
            "PKG-INFO": b"Name: example\nVersion: 1.2.3\n",
            "example/generated.c": b"/* upstream generated C */\n",
        }
        with tarfile.open(self.archive, "w:gz") as archive:
            for name, contents in self.files.items():
                member = tarfile.TarInfo("example-1.2.3/" + name)
                member.size = len(contents)
                archive.addfile(member, io.BytesIO(contents))
        self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.source = SdistSource(
            "example",
            "1.2.3",
            self.archive.as_uri(),
            self.digest,
            self.archive.name,
            ".",
            Backend.SETUPTOOLS,
        )

    def test_release_source_preserves_generated_files_and_pkg_info(self):
        destination = self.root / "prepared"
        prepare_sdist(self.source, destination)
        for name, contents in self.files.items():
            self.assertEqual((destination / name).read_bytes(), contents)

    def test_wrong_hash_is_rejected_without_extracting_a_source(self):
        destination = self.root / "downloaded.tar.gz"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            download(self.archive.as_uri(), "0" * 64, destination)
        self.assertFalse(destination.exists())

    def test_resolver_pins_the_explicit_official_distribution(self):
        metadata = {
            "urls": [
                {
                    "packagetype": "sdist",
                    "yanked": False,
                    "filename": self.archive.name,
                    "url": self.source.url,
                    "digests": {"sha256": self.digest},
                }
            ]
        }
        original = urllib.request.urlopen

        def open_url(url, **kwargs):
            if isinstance(url, str) and url.startswith("https://pypi.org/"):
                return io.BytesIO(json.dumps(metadata).encode())
            return original(url, **kwargs)

        with patch("urllib.request.urlopen", side_effect=open_url):
            resolved = resolve_source(PyPILocation("example", "1.2.3"), ".")
        self.assertEqual(resolved, self.source)

    def test_sdist_plan_roundtrip_keeps_archive_hash_and_source_kind(self):
        plan = Plan(
            Publication.BUILD,
            (
                Target(
                    "example", self.source, PythonVersion.PY313, AndroidABI.ARM64, 24
                ),
            ),
        )
        path = self.root / "plan.json"
        plan.write(path)
        self.assertEqual(load_plan(path), plan)

    def test_recipe_sources_are_mutually_exclusive_and_ref_override_is_git_only(self):
        path = self.root / "example.toml"
        text = """name="example"
pypi-version="1.2.3"
directory="."
backend="setuptools.build_meta"
[android]
python=["3.13"]
abis=["arm64-v8a"]
api=24
"""
        path.write_text(text)
        recipe = load_recipe(path)
        self.assertEqual(recipe.source, PyPILocation("example", "1.2.3"))
        with self.assertRaisesRegex(ValueError, "Git ref 覆盖"):
            requested_builds((recipe,), "example", "recipe", "v1.2.3")
        path.write_text(
            text.replace(
                'pypi-version="1.2.3"',
                'pypi-version="1.2.3"\nrepository="owner/repo"\nref="main"',
            )
        )
        with self.assertRaises(ValueError):
            load_recipe(path)


class LegacySourceTests(unittest.TestCase):
    def test_explicit_legacy_source_preserves_missing_pep517_metadata(self):
        from scripts.pipeline.source import backend_at, legacy_backend_at

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            setup = root / "setup.py"
            setup.write_text("from setuptools import setup\nsetup()\n")
            original = setup.read_bytes()
            self.assertEqual(legacy_backend_at(root), Backend.SETUPTOOLS_LEGACY)
            with self.assertRaises(FileNotFoundError):
                backend_at(root)
            self.assertFalse((root / "pyproject.toml").exists())
            self.assertEqual(setup.read_bytes(), original)
            metadata = root / "pyproject.toml"
            metadata.write_text('[build-system]\nrequires=["setuptools", "Cython"]\n')
            original_metadata = metadata.read_bytes()
            self.assertEqual(legacy_backend_at(root), Backend.SETUPTOOLS_LEGACY)
            self.assertEqual(metadata.read_bytes(), original_metadata)

    def test_explicit_legacy_mode_cannot_replace_a_declared_backend(self):
        from scripts.pipeline.source import legacy_backend_at

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "setup.py").write_text("from setuptools import setup\nsetup()\n")
            (root / "pyproject.toml").write_text(
                '[build-system]\nbuild-backend="setuptools.build_meta"\nrequires=["setuptools"]\n'
            )
            with self.assertRaisesRegex(ValueError, "不能覆盖"):
                legacy_backend_at(root)
