"""Select affected recipes and expand independent matrix jobs."""

import re
import subprocess
from dataclasses import replace
from pathlib import Path

from scripts.build.android_python import PythonVersion
from scripts.recipes.model import (
    AllRecipes,
    BuildJob,
    BuildSelection,
    GitLocation,
    Recipe,
    RecipeBuilds,
    RecipePython,
    RecipeSelection,
    RefBuild,
    SelectedPython,
    SelectedRecipes,
)

SHARED_FILES = {
    "scripts/__init__.py",
    "pyproject.toml",
    "scripts/tooling.py",
    ".github/workflows/build-wheels.yml",
    ".github/workflows/build-android-wheel-dispatch.yml",
    ".github/workflows/build-wheel-batch.yml",
}
SHARED_PREFIXES = (
    "scripts/build/",
    "scripts/recipes/",
    "scripts/pipeline/",
    ".github/actions/",
)


def select_recipes(
    recipes: tuple[Recipe, ...], selection: RecipeSelection
) -> tuple[Recipe, ...]:
    match selection:
        case AllRecipes():
            return recipes
        case SelectedRecipes(names=names):
            by_name = {recipe.name: recipe for recipe in recipes}
            unknown = set(names.values) - by_name.keys()
            if unknown:
                raise ValueError(f"未知 recipe：{', '.join(sorted(unknown))}")
            return tuple(by_name[name] for name in names.values)


PUBLICATION_FILES = {"scripts/pipeline/publish.py", "scripts/pipeline/notifications.py"}
PUBLICATION_PREFIX = ".github/actions/publish-wheels/"


def affected_recipes(
    recipes: tuple[Recipe, ...], changed: tuple[str, ...]
) -> tuple[Recipe, ...]:
    if any(
        (path in SHARED_FILES or path.startswith(SHARED_PREFIXES))
        and path not in PUBLICATION_FILES
        and not path.startswith(PUBLICATION_PREFIX)
        and "tests" not in path.split("/")
        and not path.endswith(".pyc")
        for path in changed
    ):
        return recipes
    return tuple(
        recipe for recipe in recipes if f"recipes/{recipe.name}.toml" in changed
    )


def changed_paths(repository: Path, before: str, after: str) -> tuple[str, ...]:
    output = subprocess.check_output(
        ["git", "diff", "--name-only", "--no-renames", "-z", before, after],
        cwd=repository,
    )
    return tuple(path.decode("utf-8") for path in output.split(b"\0") if path)


def build_jobs(selection: BuildSelection) -> tuple[BuildJob, ...]:
    match selection:
        case RecipeBuilds(recipes=recipes, python=python):
            selected = recipes
        case RefBuild(recipe=recipe, ref=ref, python=python):
            selected = (
                replace(recipe, source=GitLocation(recipe.source.repository, ref)),
            )
    jobs = []
    for recipe in selected:
        match python:
            case RecipePython():
                versions = recipe.android.python.values
            case SelectedPython(versions=requested):
                versions = requested.values
        jobs.extend(BuildJob(recipe, version) for version in versions)
    return tuple(jobs)


def artifact_prefix(library: str, python: PythonVersion) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", library):
        raise ValueError(f"无效的 artifact 包名：{library!r}")
    return f"{library}-android-{python.value}-wheel"
