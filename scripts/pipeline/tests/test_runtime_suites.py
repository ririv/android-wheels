"""Verify suite composition uses pinned dependencies and the selected smoke test."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build.android_python import AndroidABI
from scripts.pipeline.model import load_plan
from scripts.testing.runtime_suites import SUITES, ArtifactLayout, RuntimeSuite
from scripts.testing.scientific_runtime import main, published_dependencies


class RuntimeSuiteTests(unittest.TestCase):
    def test_data_suite_uses_published_numpy_and_pandas_on_both_abis(self):
        suite = SUITES[RuntimeSuite.DATA]
        for abi in AndroidABI:
            with self.subTest(abi=abi), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                with patch(
                    "scripts.testing.scientific_runtime.download",
                    side_effect=lambda url, sha, destination: destination,
                ) as fetch:
                    arguments = published_dependencies(abi.value, root, suite.published)
                plan = load_plan(root / "published-plan.json")
                self.assertEqual(
                    {target.library for target in plan.targets}, {"numpy", "pandas"}
                )
                self.assertTrue(all(target.abi == abi for target in plan.targets))
                self.assertEqual(len(arguments), 6)
                self.assertEqual(fetch.call_count, 2)

    def test_data_command_uses_selected_layout_dependencies_and_script(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            output = root / "output"
            argv = [
                "scientific_runtime",
                "--runs",
                "123",
                "--suite",
                "data",
                "--layout",
                "repackaged",
                "--abi",
                "x86_64",
                "--output",
                str(output),
                "--adb",
                "/adb",
                "--serial",
                "emulator-1",
                "--toolchain",
                "/toolchain",
                "--report",
                str(root / "report.json"),
            ]
            with (
                patch("sys.argv", argv),
                patch(
                    "scripts.testing.scientific_runtime.build_dependencies",
                    autospec=True,
                    return_value=(root / "plan.json", root / "artifact", []),
                ) as build,
                patch(
                    "scripts.testing.scientific_runtime.published_dependencies",
                    autospec=True,
                    return_value=[],
                ) as published,
                patch(
                    "scripts.testing.scientific_runtime.download",
                    side_effect=lambda url, sha, destination: destination,
                ),
                patch("scripts.testing.scientific_runtime.subprocess.run") as run,
            ):
                main()
            suite = SUITES[RuntimeSuite.DATA]
            build.assert_called_once_with(
                "123", "x86_64", output, ArtifactLayout.REPACKAGED, suite
            )
            published.assert_called_once_with("x86_64", output, suite.published)
            command = run.call_args.args[0]
            self.assertEqual(
                Path(command[command.index("--script") + 1]).name, "data_smoke.py"
            )
            self.assertEqual(command.count("--pure-dependency"), 4)
            self.assertIn("--report", command)
