"""Verify recipe boundaries and parallel build planning."""

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.recipes.load import load_recipe, load_recipes
from scripts.recipes.model import (
    AllRecipes,
    Choices,
    Publication,
    RecipeBuilds,
    RefBuild,
    SelectedPython,
    SelectedRecipes,
)
from scripts.recipes.plan import (
    affected_recipes,
    android_matrix,
    build_jobs,
    changed_paths,
    matrix,
    select_recipes,
    write_outputs,
)

ROOT = Path(__file__).resolve().parents[3]


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.recipes = load_recipes(ROOT / "recipes")
        self.core = next(
            recipe for recipe in self.recipes if recipe.name == "pydantic-core"
        )

    def test_migrated_recipes_keep_sources_and_special_directories(self):
        self.assertEqual(len(self.recipes), 10)
        by_name = {recipe.name: recipe for recipe in self.recipes}
        self.assertEqual(by_name["jiter"].directory, "crates/jiter-python")
        self.assertEqual(by_name["regex"].ref, "hg")
        self.assertEqual(by_name["orjson"].repository, "ririv/orjson")
        self.assertEqual(by_name["ormsgpack"].repository, "ormsgpack/ormsgpack")
        self.assertEqual(by_name["pyyaml"].backend.value, "_pyyaml_pep517")
        self.assertTrue(
            all(
                recipe.android.python.values == (PythonVersion.PY313,)
                for recipe in self.recipes
            )
        )

    def test_named_selection_and_default_parallel_plan(self):
        selected = select_recipes(
            self.recipes, SelectedRecipes(Choices("pydantic-core", ("xxhash",)))
        )
        jobs = build_jobs(RecipeBuilds(selected))
        rows = matrix(jobs, Publication.PUBLISH)["include"]
        self.assertEqual([row["name"] for row in rows], ["pydantic-core", "xxhash"])
        self.assertTrue(all(row["python"] == "3.13" for row in rows))
        self.assertTrue(all(row["publication"] == "publish" for row in rows))
        self.assertEqual(
            len(build_jobs(RecipeBuilds(select_recipes(self.recipes, AllRecipes())))),
            10,
        )

    def test_multiple_python_versions_keep_artifact_scopes_unique(self):
        selected = select_recipes(
            self.recipes, SelectedRecipes(Choices("pydantic-core", ("xxhash",)))
        )
        jobs = build_jobs(
            RecipeBuilds(
                selected,
                SelectedPython(Choices(PythonVersion.PY310, (PythonVersion.PY313,))),
            )
        )
        rows = matrix(jobs, Publication.BUILD)["include"]
        artifact_names = [
            target["artifact_name"]
            for job in jobs
            for target in android_matrix(
                job.recipe.android.abis, job.recipe.name, job.python
            )["include"]
        ]
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(artifact_names), 8)
        self.assertEqual(len(set(artifact_names)), 8)
        self.assertTrue(all(row["publication"] == "build" for row in rows))

    def test_single_recipe_ref_override(self):
        jobs = build_jobs(RefBuild(self.core, "v2.41.5"))
        self.assertEqual(jobs[0].ref, "v2.41.5")
        self.assertEqual(self.core.ref, "main")

    def test_cli_writes_multi_version_plan_and_rejects_ambiguous_ref_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            base = [
                sys.executable,
                "-B",
                "-m",
                "scripts.recipes",
                "plan",
                "--github-output",
                str(output),
            ]
            subprocess.run(
                [
                    *base,
                    "--recipes",
                    "pydantic-core",
                    "--python-versions",
                    "3.10,3.13",
                    "--version-tag",
                    "v2.41.5",
                    "--publication",
                    "build",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            values = dict(
                line.split("=", 1) for line in output.read_text().splitlines()
            )
            rows = json.loads(values["matrix"])["include"]
            self.assertEqual(values["has_jobs"], "true")
            self.assertEqual([row["python"] for row in rows], ["3.10", "3.13"])
            self.assertTrue(
                all(
                    row["ref"] == "v2.41.5" and row["publication"] == "build"
                    for row in rows
                )
            )
            output.unlink()
            result = subprocess.run(
                [
                    *base,
                    "--recipes",
                    "pydantic-core,xxhash",
                    "--version-tag",
                    "v2.41.5",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("只选择一个", result.stderr)
            self.assertFalse(output.exists())

    def test_initial_push_plans_all_existing_recipes(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "scripts.recipes",
                    "plan-changes",
                    "--before",
                    "0" * 40,
                    "--after",
                    "a" * 40,
                    "--github-output",
                    str(output),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            values = dict(
                line.split("=", 1) for line in output.read_text().splitlines()
            )
            self.assertEqual(len(json.loads(values["matrix"])["include"]), 10)

    def test_single_recipe_change_selects_only_that_package(self):
        selected = affected_recipes(
            self.recipes, ("recipes/pydantic-core.toml", "README.md")
        )
        self.assertEqual([recipe.name for recipe in selected], ["pydantic-core"])
        self.assertEqual(affected_recipes(self.recipes, ("docs/recipes.md",)), ())
        self.assertEqual(
            affected_recipes(self.recipes, ("recipes/deleted-package.toml",)), ()
        )

    def test_shared_builder_and_planner_changes_select_all(self):
        for path in [
            "scripts/build/build_android_wheel.py",
            "scripts/recipes/plan.py",
            ".github/workflows/build-android-wheel-dispatch.yml",
        ]:
            with self.subTest(path=path):
                self.assertEqual(affected_recipes(self.recipes, (path,)), self.recipes)

    def test_targets_derive_cibuildwheel_names_and_rust_triplets(self):
        target = android_matrix(
            Choices(AndroidABI.X86_64), "pydantic-core", PythonVersion.PY310
        )["include"]
        self.assertEqual(
            target,
            [
                {
                    "abi": "x86_64",
                    "cibw_arch": "x86_64",
                    "target": "x86_64-linux-android",
                    "artifact_name": "pydantic-core-android-3.10-wheel-x86_64",
                }
            ],
        )
        target = android_matrix(
            Choices(AndroidABI.ARM64), "pydantic-core", PythonVersion.PY310
        )["include"][0]
        self.assertEqual(target["abi"], "arm64-v8a")
        self.assertEqual(target["cibw_arch"], "arm64_v8a")
        self.assertEqual(target["target"], "aarch64-linux-android")

    def test_output_empty_plan_skips_matrix_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            write_outputs(output, matrix((), Publication.PUBLISH))
            values = dict(
                line.split("=", 1) for line in output.read_text().splitlines()
            )
            self.assertEqual(values["has_jobs"], "false")
            self.assertEqual(json.loads(values["matrix"]), {"include": []})

    def test_configured_python_and_abi_subsets_are_preserved(self):
        target = replace(
            self.core.android,
            python=Choices(PythonVersion.PY310),
            abis=Choices(AndroidABI.ARM64),
        )
        recipe = replace(self.core, android=target)
        row = matrix(build_jobs(RecipeBuilds((recipe,))), Publication.PUBLISH)[
            "include"
        ][0]
        self.assertEqual(row["python"], "3.10")
        self.assertEqual(json.loads(row["abis"]), ["arm64-v8a"])

    def test_toml_boundary_rejects_unknown_missing_and_invalid_fields(self):
        original = (ROOT / "recipes/pydantic-core.toml").read_text()
        mutations = [
            original + "typo = 1\n",
            original.replace('ref = "main"\n', ""),
            original.replace('backend = "maturin"', 'backend = "unknown"'),
            original.replace('python = ["3.13"]', "python = []"),
            original.replace('python = ["3.13"]', 'python = ["3.13", "3.13"]'),
            original.replace('python = ["3.13"]', 'python = ["3.9"]'),
            original.replace('abis = ["arm64-v8a", "x86_64"]', 'abis = ["x86"]'),
            original.replace('directory = "."', 'directory = "../outside"'),
            original.replace("api = 24", "api = true"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pydantic-core.toml"
            for text in mutations:
                with self.subTest(text=text):
                    path.write_text(text)
                    with self.assertRaises(ValueError):
                        load_recipe(path)

    def test_unknown_requested_recipe_fails_before_build(self):
        with self.assertRaisesRegex(ValueError, "未知 recipe"):
            select_recipes(self.recipes, SelectedRecipes(Choices("typo")))

    def test_git_diff_tracks_renames_as_removed_and_added_recipe_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def git(*args):
                return subprocess.check_output(
                    ["git", *args], cwd=root, text=True
                ).strip()

            git("init", "-b", "main")
            (root / "recipes").mkdir()
            (root / "recipes" / "before.toml").write_text("data")
            git("add", ".")
            git(
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-m",
                "initial",
            )
            before = git("rev-parse", "HEAD")
            git("mv", "recipes/before.toml", "recipes/pydantic-core.toml")
            git(
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-m",
                "rename",
            )
            after = git("rev-parse", "HEAD")
            changed = changed_paths(root, before, after)
            self.assertEqual(
                set(changed), {"recipes/before.toml", "recipes/pydantic-core.toml"}
            )
            self.assertEqual(affected_recipes(self.recipes, changed), (self.core,))


if __name__ == "__main__":
    unittest.main()
