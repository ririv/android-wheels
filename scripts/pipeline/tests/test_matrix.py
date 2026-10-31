"""Verify bounded matrices, declared compatibility and shared wheel identities."""

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.pipeline.artifacts import collect, record
from scripts.pipeline.model import GitSource, Plan, Target, UnsupportedPython, load_plan
from scripts.pipeline.planning import (
    BATCH_SIZE,
    recipe_plan,
    write_actions_plan,
    write_batch,
)
from scripts.recipes.model import Backend, Publication
from scripts.testing.wheels import write_wheel

ROOT = Path(__file__).resolve().parents[3]
SOURCE = GitSource(
    "pydantic/pydantic-core", "main", "a" * 40, ".", Backend.MATURIN, ">=3.11,<3.15"
)


class MatrixTests(unittest.TestCase):
    def test_current_source_skips_declared_unsupported_versions_without_downgrade(self):
        event = {
            "inputs": {
                "recipes": "pydantic-core",
                "python_versions": "recipe",
                "version_tag": "",
                "publication": "build",
            }
        }
        with patch(
            "scripts.pipeline.planning.resolve_source", return_value=SOURCE
        ) as resolve:
            plan = recipe_plan("workflow_dispatch", event, ROOT)
        self.assertEqual(resolve.call_count, 1)
        self.assertEqual(
            {t.python for t in plan.targets},
            {
                PythonVersion.PY311,
                PythonVersion.PY312,
                PythonVersion.PY313,
                PythonVersion.PY314,
            },
        )
        self.assertEqual(
            plan.skipped,
            (
                UnsupportedPython(
                    "pydantic-core", PythonVersion.PY310, SOURCE.requires_python
                ),
                UnsupportedPython(
                    "pydantic-core", PythonVersion.PY315, SOURCE.requires_python
                ),
            ),
        )
        self.assertTrue(all(t.source == SOURCE for t in plan.targets))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "plan.json"
            plan.write(path)
            self.assertEqual(load_plan(path), plan)

    def test_large_plan_splits_without_omitting_or_duplicating_targets(self):
        targets = tuple(
            Target(f"package-{n}", replace(SOURCE, requires_python=""), python, abi, 24)
            for n in range(54)
            for python in PythonVersion
            for abi in AndroidABI
        )
        plan = Plan(Publication.BUILD, targets)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "output"
            write_actions_plan(plan, root / "plan.json", output)
            values = dict(
                line.split("=", 1) for line in output.read_text().splitlines()
            )
            batches = json.loads(values["matrix"])["include"]
            self.assertLess(len(values["matrix"]), 1024)
            rows = []
            for batch in batches:
                path = root / f"batch-{batch['batch']}"
                write_batch(plan, batch["batch"], path)
                selected = json.loads(path.read_text().removeprefix("matrix="))[
                    "include"
                ]
                self.assertLessEqual(len(selected), BATCH_SIZE)
                self.assertLess(len(path.read_text().encode("utf-16-le")), 1024 * 1024)
                rows.extend(selected)
            self.assertEqual(
                [row["artifact"] for row in rows], [t.artifact for t in targets]
            )

    def test_shared_wheel_names_publish_separately_for_all_build_origins(self):
        targets = tuple(
            Target("example", SOURCE, python, abi, 24)
            for python in (PythonVersion.PY310, PythonVersion.PY315)
            for abi in AndroidABI
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for target in targets:
                folder = root / target.artifact
                folder.mkdir()
                write_wheel(
                    folder / "example-1.0-py3-none-any.whl",
                    {
                        "example.py": target.artifact.encode(),
                        "example-1.0.dist-info/METADATA": b"Name: example\nVersion: 1.0\n",
                        "example-1.0.dist-info/WHEEL": b"Wheel-Version: 1.0\nTag: py3-none-any\n",
                    },
                )
                record(folder, target)
            wheels = collect(root, Plan(Publication.PUBLISH, targets))
            self.assertEqual(len(wheels), 4)
            self.assertEqual(len({p.name for p in wheels.values()}), 4)

    def test_link_parameters_resolve_for_each_python_version(self):
        source = replace(SOURCE, backend=Backend.SCIKIT_BUILD, requires_python=">=3.10")
        event = {
            "inputs": {
                "recipes": "argon2-cffi-bindings",
                "python_versions": "3.10,3.15",
                "version_tag": "",
                "publication": "build",
            }
        }
        with patch("scripts.pipeline.planning.resolve_source", return_value=source):
            plan = recipe_plan("workflow_dispatch", event, ROOT)
        for target in plan.targets:
            self.assertIn(f"-lpython{target.python}", target.config_settings[0].value)
            self.assertNotIn("{python}", target.config_settings[0].value)

    def test_numpy_cross_files_follow_each_target_and_checkout(self):
        source = replace(SOURCE, backend=Backend.MESON, requires_python=">=3.12")
        event = {
            "inputs": {
                "recipes": "numpy",
                "python_versions": "3.13",
                "version_tag": "",
                "publication": "build",
            }
        }
        with patch("scripts.pipeline.planning.resolve_source", return_value=source):
            plan = recipe_plan("workflow_dispatch", event, ROOT)
        self.assertEqual(len(plan.targets), 2)
        for target in plan.targets:
            value = target.config_settings[0].value
            self.assertEqual(
                value,
                f"--cross-file={{workspace}}/scripts/build/meson/{target.abi}.ini",
            )
            self.assertIn(
                f"setup-args=--cross-file={Path.cwd()}/scripts/build/meson/{target.abi}.ini",
                target.row()["cibw_config_settings"],
            )
