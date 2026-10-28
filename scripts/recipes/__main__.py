"""Command-line interface for recipe validation and Actions planning."""

import argparse
import json
from pathlib import Path

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.recipes.load import choices, load_recipes, validate_ref
from scripts.recipes.model import (
    AllRecipes,
    Backend,
    Publication,
    RecipeBuilds,
    RecipePython,
    RefBuild,
    SelectedPython,
    SelectedRecipes,
)
from scripts.recipes.plan import (
    affected_recipes,
    android_matrix,
    artifact_prefix,
    build_jobs,
    changed_paths,
    matrix,
    select_recipes,
    write_outputs,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--recipes-dir", type=Path, default=Path("recipes"))
    for name in ["plan", "plan-changes"]:
        plan = commands.add_parser(name)
        plan.add_argument("--recipes-dir", type=Path, default=Path("recipes"))
        plan.add_argument("--github-output", type=Path, required=True)
        plan.add_argument(
            "--publication", type=Publication, default=Publication.PUBLISH
        )
        if name == "plan":
            plan.add_argument("--recipes", required=True)
            plan.add_argument("--python-versions", default="recipe")
            plan.add_argument("--version-tag", default="")
        else:
            plan.add_argument("--git-dir", type=Path, default=Path("."))
            plan.add_argument("--before", required=True)
            plan.add_argument("--after", required=True)
    targets = commands.add_parser("targets")
    targets.add_argument("--abis", required=True)
    targets.add_argument("--library", required=True)
    targets.add_argument("--python-version", type=PythonVersion, required=True)
    targets.add_argument("--publication", type=Publication, required=True)
    targets.add_argument("--github-output", type=Path, required=True)
    backend = commands.add_parser("check-backend")
    backend.add_argument("--actual", required=True)
    backend.add_argument("--expected", required=True)
    args = parser.parse_args()

    if args.command == "check-backend":
        if args.expected != "detect" and Backend(args.expected).value != args.actual:
            raise ValueError(
                f"recipe 后端 {args.expected} 与源码后端 {args.actual} 不一致"
            )
        return
    if args.command == "targets":
        abis = choices(json.loads(args.abis), AndroidABI, "Android ABI")
        write_outputs(
            args.github_output, android_matrix(abis, args.library, args.python_version)
        )
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(
                f"artifact_prefix={artifact_prefix(args.library, args.python_version)}\n"
            )
        return

    recipes = load_recipes(args.recipes_dir)
    if args.command == "validate":
        print(f"已校验 {len(recipes)} 个 recipe")
        return
    if args.command == "plan":
        selection = (
            AllRecipes()
            if args.recipes == "all"
            else SelectedRecipes(choices(args.recipes.split(","), str, "recipes"))
        )
        selected = select_recipes(recipes, selection)
        python = (
            RecipePython()
            if args.python_versions == "recipe"
            else SelectedPython(
                choices(args.python_versions.split(","), PythonVersion, "Python 版本")
            )
        )
        if args.version_tag:
            if len(selected) != 1:
                raise ValueError("覆盖 Git ref 时必须只选择一个 recipe")
            request = RefBuild(selected[0], validate_ref(args.version_tag), python)
        else:
            request = RecipeBuilds(selected, python)
        jobs = build_jobs(request)
    else:
        if args.before == "0" * 40:
            selected = recipes
        else:
            selected = affected_recipes(
                recipes, changed_paths(args.git_dir, args.before, args.after)
            )
        jobs = build_jobs(RecipeBuilds(selected))
    data = matrix(jobs, args.publication)
    write_outputs(args.github_output, data)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
