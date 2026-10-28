"""Translate Actions events into pinned, independently executable targets."""

import json
import subprocess
from pathlib import Path

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.pipeline.model import Plan, Target
from scripts.pipeline.source import resolve_source
from scripts.recipes.load import load_recipes
from scripts.recipes.model import (
    GitLocation,
    LiteralEnvironment,
    Publication,
    RecipeBuilds,
    TargetEnvironment,
)
from scripts.recipes.plan import (
    affected_recipes,
    build_jobs,
    changed_paths,
)
from scripts.recipes.request import requested_builds


def recipe_plan(event_name: str, event: dict, root: Path) -> Plan:
    recipes = load_recipes(root / "recipes")
    if event_name == "push":
        before = event["before"]
        if before == "0" * 40:
            selected = recipes
        else:
            subprocess.run(
                ["git", "fetch", "--no-tags", "--depth=1", "origin", before],
                cwd=root,
                check=True,
            )
            selected = affected_recipes(
                recipes, changed_paths(root, before, event["after"])
            )
        request = RecipeBuilds(selected)
        publication = Publication.PUBLISH
    elif event_name == "workflow_dispatch":
        inputs = event["inputs"]
        request = requested_builds(
            recipes,
            inputs["recipes"],
            inputs["python_versions"],
            inputs.get("version_tag", ""),
        )
        publication = Publication(inputs["publication"])
    else:
        raise ValueError(f"不支持的事件：{event_name}")
    sources = {}
    targets = []
    for job in build_jobs(request):
        recipe = job.recipe
        key = (recipe.source, recipe.directory)
        if key not in sources:
            sources[key] = resolve_source(recipe.source, recipe.directory)
        source = sources[key]
        if source.backend != recipe.backend:
            raise ValueError(f"{recipe.name} 后端与 recipe 不一致：{source.backend}")
        targets.extend(
            Target(
                recipe.name,
                source,
                job.python,
                abi,
                recipe.android.api,
                resolve_environment(
                    recipe.environment, job.python, abi, recipe.android.api
                ),
            )
            for abi in recipe.android.abis.values
        )
    return Plan(publication, tuple(targets))


def resolve_environment(
    settings: tuple, python: PythonVersion, abi: AndroidABI, api: int
) -> tuple[LiteralEnvironment, ...]:
    fields = {
        "triplet": abi.triplet,
        "python": python.value,
        "abi": abi.value,
        "api": str(api),
    }
    result = []
    for setting in settings:
        match setting:
            case LiteralEnvironment():
                result.append(setting)
            case TargetEnvironment(name=name, target=field):
                result.append(LiteralEnvironment(name, fields[field.value]))
    return tuple(result)


def manual_plan(event: dict) -> Plan:
    inputs = event["inputs"]
    source = resolve_source(
        GitLocation(inputs["git_repository"], inputs.get("version_tag", "")),
        inputs["package_dir"],
    )
    api = int(inputs["android_api"])
    if api < 24:
        raise ValueError("Android API 必须至少为 24")
    return Plan(
        Publication(inputs["publication"]),
        tuple(
            Target(
                inputs["library_name"],
                source,
                PythonVersion(inputs["target_python_version"]),
                abi,
                api,
            )
            for abi in AndroidABI
        ),
    )


def write_actions_plan(plan: Plan, path: Path, output: Path) -> None:
    plan.write(path)
    with output.open("a", encoding="utf-8") as stream:
        stream.write(
            f"matrix={json.dumps({'include': [t.row() for t in plan.targets]}, separators=(',', ':'))}\n"
        )
        stream.write(f"has_jobs={str(bool(plan.targets)).lower()}\n")
        stream.write(f"publication={plan.publication.value}\n")
