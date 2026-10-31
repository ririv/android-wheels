"""Keep checkout configuration paths stable when the build tool changes cwd."""

import os
import tempfile
import unittest
from pathlib import Path

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.build.chaquopy_adapter import prepare_builder
from scripts.pipeline.model import GitSource, Target
from scripts.recipes.model import Backend, ConfigSetting


class ChaquopyAdapterTests(unittest.TestCase):
    def test_meson_cross_file_uses_explicit_workspace_after_chdir(self):
        with tempfile.TemporaryDirectory() as temporary:
            pypi = Path(temporary)
            (pypi / "build-wheel.py").write_text(
                "class BuildWheel:\n"
                "    def create_host_env(self): pass\n"
                "    def create_build_env(self): self.received = self.builder.settings\n"
                "    def get_common_env_vars(self, env): pass\n"
                "    def get_rust_env_vars(self, env): pass\n"
            )
            target = Target(
                "numpy",
                GitSource("numpy/numpy", "main", "a" * 40, ".", Backend.MESON),
                PythonVersion.PY312,
                AndroidABI.ARM64,
                24,
                config_settings=(
                    ConfigSetting("setup-args", "--cross-file={workspace}/arm64.ini"),
                ),
            )
            builder = prepare_builder(pypi, target, Path("/checkout with spaces"))
            builder.builder = object()
            original = Path.cwd()
            try:
                os.chdir(pypi)
                builder.create_build_env()
            finally:
                os.chdir(original)
            self.assertEqual(
                builder.received,
                {"setup-args": "--cross-file=/checkout with spaces/arm64.ini"},
            )
