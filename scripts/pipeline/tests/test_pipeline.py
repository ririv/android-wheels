"""Exercise pinned planning, artifact integrity and atomic publication."""

import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.pipeline.artifacts import collect, record, verify_wheel
from scripts.pipeline.cargo_env import configure
from scripts.pipeline.model import Builder, Plan, Source, Target, load_plan
from scripts.pipeline.planning import recipe_plan
from scripts.pipeline.publish import Published, Unchanged, publish
from scripts.pipeline.source import backend_at, verify_checkout
from scripts.recipes.load import load_recipes
from scripts.recipes.model import Backend, Publication
from scripts.recipes.plan import affected_recipes
from scripts.testing.wheels import write_wheel

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Source("pydantic/pydantic-core", "v2.41.5", "a" * 40, ".", Backend.MATURIN)
TARGET = Target("pydantic-core", SOURCE, PythonVersion.PY313, AndroidABI.ARM64, 24)


def make_wheel(
    directory,
    target=TARGET,
    python="cp313",
    abi="cp313",
    platform="android_24_arm64_v8a",
):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"pydantic_core-2.41.5-{python}-{abi}-{platform}.whl"
    prefix = "pydantic_core-2.41.5.dist-info/"
    write_wheel(
        path,
        {
            prefix + "METADATA": b"Name: pydantic-core\nVersion: 2.41.5\n",
            prefix
            + "WHEEL": f"Wheel-Version: 1.0\nTag: {python}-{abi}-{platform}\n".encode(),
            "pydantic_core/__init__.py": b"",
        },
    )
    record(directory, target)
    return path


class PipelineTests(unittest.TestCase):
    def test_initial_push_uses_the_production_flat_plan(self):
        recipes = load_recipes(ROOT / "recipes")
        by_source = {
            (r.repository, r.ref, r.directory): Source(
                r.repository, r.ref, "a" * 40, r.directory, r.backend
            )
            for r in recipes
        }
        with patch(
            "scripts.pipeline.planning.resolve_source",
            side_effect=lambda *key: by_source[key],
        ):
            plan = recipe_plan("push", {"before": "0" * 40}, ROOT)
        self.assertEqual(len(plan.targets), 20)
        self.assertEqual(len({t.artifact for t in plan.targets}), 20)

    def test_push_of_publication_code_does_not_resolve_or_compile_sources(self):
        with (
            patch("scripts.pipeline.planning.subprocess.run"),
            patch(
                "scripts.pipeline.planning.changed_paths",
                return_value=(
                    "scripts/pipeline/publish.py",
                    ".github/actions/publish-wheels/action.yml",
                ),
            ),
            patch("scripts.pipeline.planning.resolve_source") as resolve,
        ):
            plan = recipe_plan("push", {"before": "a" * 40, "after": "b" * 40}, ROOT)
        self.assertEqual(plan.targets, ())
        resolve.assert_not_called()

    def test_ambiguous_ref_override_fails_before_source_resolution(self):
        event = {
            "inputs": {
                "recipes": "pydantic-core,xxhash",
                "python_versions": "recipe",
                "version_tag": "v1",
                "publication": "build",
            }
        }
        with patch("scripts.pipeline.planning.resolve_source") as resolve:
            with self.assertRaisesRegex(ValueError, "只选择一个"):
                recipe_plan("workflow_dispatch", event, ROOT)
        resolve.assert_not_called()

    def test_multi_python_plan_resolves_each_source_once_and_keeps_flat_parallel_targets(
        self,
    ):
        event = {
            "inputs": {
                "recipes": "pydantic-core",
                "python_versions": "3.10,3.13",
                "version_tag": "v2.41.5",
                "publication": "build",
            }
        }
        with patch(
            "scripts.pipeline.planning.resolve_source", return_value=SOURCE
        ) as resolve:
            plan = recipe_plan("workflow_dispatch", event, ROOT)
        self.assertEqual(resolve.call_count, 1)
        self.assertEqual(len(plan.targets), 4)
        self.assertEqual(len({t.artifact for t in plan.targets}), 4)
        self.assertEqual({t.source.sha for t in plan.targets}, {SOURCE.sha})
        self.assertEqual(plan.publication, Publication.BUILD)

    def test_builder_selection_keeps_all_existing_paths(self):
        self.assertEqual(TARGET.builder, Builder.MATURIN)
        c_target = replace(TARGET, source=replace(SOURCE, backend=Backend.SETUPTOOLS))
        self.assertEqual(c_target.builder, Builder.CIBUILDWHEEL)
        self.assertEqual(
            replace(c_target, python=PythonVersion.PY310).builder, Builder.CHAQUOPY
        )

    def test_plan_round_trip_preserves_source_and_targets(self):
        plan = Plan(Publication.PUBLISH, (TARGET,))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            plan.write(path)
            self.assertEqual(load_plan(path), plan)

    def test_tests_and_bytecode_do_not_trigger_native_builds(self):
        recipes = load_recipes(ROOT / "recipes")
        self.assertEqual(
            affected_recipes(
                recipes,
                (
                    "scripts/build/tests/test_android_python.py",
                    "scripts/pipeline/tests/test_pipeline.py",
                    "scripts/build/__pycache__/x.pyc",
                    "scripts/pipeline/publish.py",
                    "scripts/pipeline/notifications.py",
                    ".github/actions/publish-wheels/action.yml",
                ),
            ),
            (),
        )
        self.assertEqual(
            affected_recipes(recipes, ("scripts/pipeline/artifacts.py",)), recipes
        )

    def test_complete_artifacts_are_collected_and_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wheel = make_wheel(root / TARGET.artifact)
            plan = Plan(Publication.PUBLISH, (TARGET,))
            self.assertEqual(list(collect(root, plan)), [f"pydantic-core/{wheel.name}"])
            wheel.write_bytes(wheel.read_bytes() + b"modified")
            with self.assertRaisesRegex(ValueError, "哈希"):
                collect(root, plan)

    def test_missing_artifact_and_empty_output_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "集合不完整"):
                collect(root, Plan(Publication.PUBLISH, (TARGET,)))
            with self.assertRaisesRegex(ValueError, "一个 wheel"):
                record(root, TARGET)

    def test_manifest_cannot_claim_another_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_wheel(root / TARGET.artifact)
            changed = replace(TARGET, source=replace(SOURCE, sha="b" * 40))
            with self.assertRaisesRegex(ValueError, "来源"):
                collect(root, Plan(Publication.PUBLISH, (changed,)))

    def test_chaquopy_optional_build_tag_preserves_package_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / TARGET.artifact
            wheel = make_wheel(directory)
            wheel.rename(directory / wheel.name.replace("2.41.5-", "2.41.5-0-"))
            record(directory, TARGET)
            wheels = collect(Path(tmp), Plan(Publication.PUBLISH, (TARGET,)))
            self.assertEqual(len(wheels), 1)
            self.assertIn("2.41.5-0-cp313", next(iter(wheels)))

    def test_wheel_targets_allow_abi3_and_reject_wrong_architecture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wheel = make_wheel(root / "stable", python="cp39", abi="abi3")
            verify_wheel(wheel, TARGET)
            with self.assertRaisesRegex(ValueError, "平台"):
                verify_wheel(wheel, replace(TARGET, abi=AndroidABI.X86_64))

    def test_backend_requires_the_explicit_project_and_never_searches_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "nested"
            child.mkdir()
            (child / "pyproject.toml").write_text(
                '[build-system]\nbuild-backend="maturin"\n'
            )
            self.assertEqual(backend_at(child), Backend.MATURIN)
            with self.assertRaises(FileNotFoundError):
                backend_at(root)

    def test_cargo_environment_preserves_upstream_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cargo").mkdir()
            path = root / ".cargo/config.toml"
            path.write_text('[build]\njobs=2\n[env]\nKEEP="yes"\n')
            configure(root, Path("/runtime/env"))
            import tomllib

            data = tomllib.loads(path.read_text())
            self.assertEqual(data["build"]["jobs"], 2)
            self.assertEqual(data["env"]["KEEP"], "yes")
            self.assertEqual(
                data["env"]["PYO3_CROSS_LIB_DIR"], "/runtime/python/prefix/lib"
            )


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.remote = self.root / "remote.git"
        self.repo = self.root / "repo"
        self.run_git(self.root, "init", "--bare", str(self.remote))
        self.run_git(self.root, "clone", str(self.remote), str(self.repo))
        self.run_git(self.repo, "checkout", "-b", "wheels")
        (self.repo / "existing.txt").write_text("preserved")
        self.run_git(self.repo, "add", ".")
        self.run_git(self.repo, "commit", "-m", "initial")
        self.run_git(self.repo, "push", "origin", "wheels")

    def run_git(self, cwd, *args):
        return subprocess.check_output(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                *args,
            ],
            cwd=cwd,
            text=True,
            stderr=subprocess.PIPE,
        ).strip()

    def test_publication_is_one_commit_and_unchanged_artifacts_are_not_republished(
        self,
    ):
        first = self.run_git(self.repo, "rev-parse", "HEAD")
        wheel = self.root / "new.whl"
        wheel.write_bytes(b"verified wheel")
        wheels = {"example/new.whl": wheel}
        result = publish(self.repo, wheels, "test-run")
        self.assertIsInstance(result, Published)
        self.assertEqual(
            self.run_git(self.remote, "rev-list", "--count", "wheels"), "2"
        )
        self.assertEqual(
            self.run_git(self.remote, "show", "wheels:existing.txt"), "preserved"
        )
        self.assertEqual(
            self.run_git(self.remote, "show", "wheels:example/new.whl"),
            "verified wheel",
        )
        again = publish(self.repo, wheels, "test-run")
        self.assertIsInstance(again, Unchanged)
        self.assertEqual(result.revision, again.revision)
        self.assertNotEqual(first, result.revision)

    def test_changed_remote_is_reapplied_without_losing_other_publications(self):
        wheel = self.root / "new.whl"
        wheel.write_bytes(b"verified wheel")
        original = subprocess.run
        injected = False

        def concurrent_run(args, **kwargs):
            nonlocal injected
            if args[:2] == ["git", "push"] and not injected:
                injected = True
                (self.repo / "other.txt").write_text("other publication")
                self.run_git(self.repo, "add", "other.txt")
                self.run_git(self.repo, "commit", "-m", "concurrent")
                self.run_git(self.repo, "push", "origin", "wheels")
            return original(args, **kwargs)

        with patch(
            "scripts.pipeline.publish.subprocess.run", side_effect=concurrent_run
        ):
            result = publish(self.repo, {"example/new.whl": wheel}, "test-run")
        self.assertIsInstance(result, Published)
        self.assertEqual(
            self.run_git(self.remote, "show", "wheels:other.txt"), "other publication"
        )

    def test_checkout_must_match_the_resolved_sha(self):
        (self.repo / "pyproject.toml").write_text(
            '[build-system]\nbuild-backend="maturin"\n'
        )
        sha = self.run_git(self.repo, "rev-parse", "HEAD")
        verify_checkout(replace(SOURCE, sha=sha), self.repo)
        with self.assertRaisesRegex(ValueError, "提交不匹配"):
            verify_checkout(SOURCE, self.repo)


if __name__ == "__main__":
    unittest.main()
