"""Verify declared build environment survives planning and artifact collection."""

import shlex
import tempfile
import unittest
from pathlib import Path

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.pipeline.artifacts import collect, record
from scripts.pipeline.model import GitSource, Plan, Target, load_plan
from scripts.recipes.load import environment, load_recipe
from scripts.recipes.model import Backend, EnvironmentVariable, Publication
from scripts.testing.wheels import write_wheel


class EnvironmentTests(unittest.TestCase):
    def test_recipe_reads_explicit_native_build_switches(self):
        root = Path(__file__).resolve().parents[3]
        recipe = load_recipe(root / "recipes/chardet.toml")
        self.assertEqual(recipe.backend, Backend.HATCHLING)
        self.assertEqual(
            recipe.environment,
            (
                EnvironmentVariable("HATCH_BUILD_HOOK_ENABLE_CUSTOM", "true"),
                EnvironmentVariable("HATCH_BUILD_HOOK_ENABLE_MYPYC", "true"),
                EnvironmentVariable("PIP_NO_BINARY", "mypy"),
            ),
        )

    def test_environment_is_literal_and_does_not_override_the_builder(self):
        values = {"PACKAGE_FLAGS": "a 'quoted' $HOME $(command)"}
        variables = environment(values)
        target = Target(
            "example",
            GitSource("owner/repo", "main", "a" * 40, ".", Backend.SETUPTOOLS),
            PythonVersion.PY313,
            AndroidABI.ARM64,
            24,
            variables,
        )
        self.assertEqual(
            shlex.split(target.row()["cibw_environment"]),
            ["PACKAGE_FLAGS=" + values["PACKAGE_FLAGS"]],
        )
        for name in (
            "PATH",
            "CC",
            "CIBW_BEFORE_BUILD",
            "GITHUB_ENV",
            "HOST_PYTHON",
            "CARGO_TARGET_AARCH64_LINUX_ANDROID_RUSTFLAGS",
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                environment({name: "override"})
        for value in (True, "first\nsecond", "first\rsecond", "first\0second"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                environment({"PACKAGE_FLAGS": value})

    def test_environment_roundtrip_and_manifest_match_after_json_encoding(self):
        target = Target(
            "example",
            GitSource("owner/repo", "main", "a" * 40, ".", Backend.SETUPTOOLS),
            PythonVersion.PY313,
            AndroidABI.ARM64,
            24,
            (EnvironmentVariable("PACKAGE_FLAGS", "native"),),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = Plan(Publication.BUILD, (target,))
            plan.write(root / "plan.json")
            loaded = load_plan(root / "plan.json")
            self.assertEqual(loaded, plan)
            folder = root / "artifacts" / target.artifact
            folder.mkdir(parents=True)
            wheel = folder / "example-1.0-cp313-cp313-android_24_arm64_v8a.whl"
            prefix = "example-1.0.dist-info/"
            write_wheel(
                wheel,
                {
                    prefix + "METADATA": b"Name: example\nVersion: 1.0\n",
                    prefix
                    + "WHEEL": b"Wheel-Version: 1.0\nTag: cp313-cp313-android_24_arm64_v8a\n",
                },
            )
            record(folder, loaded.targets[0])
            self.assertEqual(
                list(collect(root / "artifacts", loaded).values()), [wheel]
            )
