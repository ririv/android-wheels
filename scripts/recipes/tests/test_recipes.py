"""Verify recipe boundaries and parallel build planning."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.build.android_python import PythonVersion
from scripts.recipes.load import load_recipe, load_recipes
from scripts.recipes.model import (
    AllRecipes,
    Choices,
    RecipeBuilds,
    RefBuild,
    SelectedPython,
    SelectedRecipes,
)
from scripts.recipes.plan import (
    affected_recipes,
    build_jobs,
    changed_paths,
    select_recipes,
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
        self.assertEqual([job.recipe.name for job in jobs], ["pydantic-core", "xxhash"])
        self.assertTrue(all(job.python == PythonVersion.PY313 for job in jobs))
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
        self.assertEqual(len(jobs), 4)
        self.assertEqual(
            {job.python for job in jobs}, {PythonVersion.PY310, PythonVersion.PY313}
        )

    def test_single_recipe_ref_override(self):
        jobs = build_jobs(RefBuild(self.core, "v2.41.5"))
        self.assertEqual(jobs[0].ref, "v2.41.5")
        self.assertEqual(self.core.ref, "main")

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
