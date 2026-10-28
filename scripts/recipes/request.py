"""Parse explicit package, Python and ref selections at the input boundary."""

from scripts.build.android_python import PythonVersion
from scripts.recipes.load import choices, validate_ref
from scripts.recipes.model import (
    AllRecipes,
    BuildSelection,
    Recipe,
    RecipeBuilds,
    RecipePython,
    RefBuild,
    SelectedPython,
    SelectedRecipes,
)
from scripts.recipes.plan import select_recipes


def requested_builds(
    recipes: tuple[Recipe, ...], names: str, versions: str, ref: str
) -> BuildSelection:
    selected = select_recipes(
        recipes,
        AllRecipes()
        if names == "all"
        else SelectedRecipes(choices(names.split(","), str, "recipes")),
    )
    python = (
        RecipePython()
        if versions == "recipe"
        else SelectedPython(choices(versions.split(","), PythonVersion, "Python 版本"))
    )
    if ref:
        if len(selected) != 1:
            raise ValueError("覆盖 Git ref 时必须只选择一个 recipe")
        return RefBuild(selected[0], validate_ref(ref), python)
    return RecipeBuilds(selected, python)
