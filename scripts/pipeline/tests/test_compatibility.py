"""Keep upstream exclusions limited to the exact source which failed."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from scripts.build.android_python import PythonVersion
from scripts.pipeline.compatibility import GitCommit, UpstreamUnsupported
from scripts.pipeline.model import GitSource, load_plan
from scripts.pipeline.planning import recipe_plan
from scripts.recipes.model import Backend

ROOT = Path(__file__).resolve().parents[3]
SOURCE = GitSource(
    "pydantic/pydantic-core",
    "main",
    "383eb95a19433754c0cecf7025b50c26b6d97a36",
    ".",
    Backend.MATURIN,
    ">=3.9",
)


class CompatibilityTests(unittest.TestCase):
    def plan(self, source):
        event = {
            "inputs": {
                "recipes": "pydantic-core",
                "python_versions": "3.14,3.15",
                "version_tag": "",
                "publication": "build",
            }
        }
        with patch("scripts.pipeline.planning.resolve_source", return_value=source):
            return recipe_plan("workflow_dispatch", event, ROOT)

    def test_evidenced_exclusion_does_not_block_a_new_upstream_commit(self):
        plan = self.plan(SOURCE)
        self.assertEqual({t.python for t in plan.targets}, {PythonVersion.PY314})
        exclusion = plan.skipped[0]
        self.assertIsInstance(exclusion, UpstreamUnsupported)
        self.assertEqual(exclusion.source, GitCommit(SOURCE.sha))
        updated = self.plan(replace(SOURCE, sha="a" * 40))
        self.assertEqual(
            {t.python for t in updated.targets},
            {PythonVersion.PY314, PythonVersion.PY315},
        )
        self.assertEqual(updated.skipped, ())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "plan.json"
            plan.write(path)
            self.assertEqual(load_plan(path), plan)
