"""Verify the lazy Fortran launcher isolates its compiler from legacy wrappers."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.build.fortran import configure_fortran


class FortranTests(unittest.TestCase):
    def test_launcher_selects_real_compiler_and_preserves_argument_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shim = root / "flang-new"
            shim.write_text('#!/bin/sh\nprintf "%s\\n" "$CC" "$@"\n')
            shim.chmod(0o755)
            environment = {"CC": "/legacy/compiler-wrapper"}

            def install(env):
                env["FC"] = str(shim)

            compiler = root / "NDK with spaces/bin/aarch64-linux-android26-clang"
            configure_fortran(environment, compiler, install)
            output = subprocess.check_output(
                [environment["FC"], "--version", "argument with spaces"],
                env={**os.environ, **environment},
                text=True,
            )
            self.assertEqual(
                output.splitlines(),
                [str(compiler), "--version", "argument with spaces"],
            )
            self.assertEqual(environment["CC"], "/legacy/compiler-wrapper")
