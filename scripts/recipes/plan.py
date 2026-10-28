"""Select affected recipes and expand independent matrix jobs."""

import json
import re
import subprocess
from dataclasses import replace
from pathlib import Path

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.recipes.model import (
    AllRecipes,
    BuildJob,
    BuildSelection,
    Choices,
    Publication,
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
    "requirements/build.txt",
    ".github/workflows/build-wheels.yml",
    ".github/workflows/build-android-wheel-dispatch.yml",
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


def affected_recipes(
    recipes: tuple[Recipe, ...], changed: tuple[str, ...]
) -> tuple[Recipe, ...]:
    if any(
        (path in SHARED_FILES or path.startswith(SHARED_PREFIXES))
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
            selected = (replace(recipe, ref=ref),)
    jobs = []
    for recipe in selected:
        match python:
            case RecipePython():
                versions = recipe.android.python.values
            case SelectedPython(versions=requested):
                versions = requested.values
        jobs.extend(BuildJob(recipe, version) for version in versions)
    return tuple(jobs)


def matrix(jobs: tuple[BuildJob, ...], publication: Publication) -> dict:
    return {
        "include": [
            {
                "name": job.recipe.name,
                "platform": "android",
                "repository": job.recipe.repository,
                "ref": job.ref,
                "directory": job.recipe.directory,
                "backend": job.recipe.backend.value,
                "python": job.python.value,
                "abis": json.dumps(
                    [abi.value for abi in job.recipe.android.abis.values]
                ),
                "android_api": str(job.recipe.android.api),
                "publication": publication.value,
            }
            for job in jobs
        ]
    }


def artifact_prefix(library: str, python: PythonVersion) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", library):
        raise ValueError(f"无效的 artifact 包名：{library!r}")
    return f"{library}-android-{python.value}-wheel"


def android_matrix(
    abis: Choices[AndroidABI], library: str, python: PythonVersion
) -> dict:
    prefix = artifact_prefix(library, python)
    return {
        "include": [
            {
                "abi": abi.value,
                "cibw_arch": abi.value.replace("-", "_"),
                "target": abi.triplet,
                "artifact_name": f"{prefix}-{abi.value}",
            }
            for abi in abis.values
        ]
    }


def write_outputs(path: Path, data: dict) -> None:
    with path.open("a", encoding="utf-8") as output:
        output.write(f"matrix={json.dumps(data, separators=(',', ':'))}\n")
        output.write(f"has_jobs={str(bool(data['include'])).lower()}\n")
