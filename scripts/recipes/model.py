"""Represent recipe data and explicit build selections."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

from scripts.build.android_python import AndroidABI, PythonVersion

T = TypeVar("T")


@dataclass(frozen=True)
class Choices(Generic[T]):
    first: T
    rest: tuple[T, ...] = ()

    @property
    def values(self) -> tuple[T, ...]:
        return (self.first, *self.rest)


class Backend(StrEnum):
    MATURIN = "maturin"
    SETUPTOOLS = "setuptools.build_meta"
    PYYAML = "_pyyaml_pep517"


class Publication(StrEnum):
    PUBLISH = "publish"
    BUILD = "build"


@dataclass(frozen=True)
class Android:
    python: Choices[PythonVersion]
    abis: Choices[AndroidABI]
    api: int


@dataclass(frozen=True)
class Recipe:
    name: str
    repository: str
    ref: str
    directory: str
    backend: Backend
    android: Android


@dataclass(frozen=True)
class AllRecipes:
    pass


@dataclass(frozen=True)
class SelectedRecipes:
    names: Choices[str]


RecipeSelection = AllRecipes | SelectedRecipes


@dataclass(frozen=True)
class RecipePython:
    pass


@dataclass(frozen=True)
class SelectedPython:
    versions: Choices[PythonVersion]


PythonSelection = RecipePython | SelectedPython


@dataclass(frozen=True)
class RecipeBuilds:
    recipes: tuple[Recipe, ...]
    python: PythonSelection = RecipePython()


@dataclass(frozen=True)
class RefBuild:
    recipe: Recipe
    ref: str
    python: PythonSelection = RecipePython()


BuildSelection = RecipeBuilds | RefBuild


@dataclass(frozen=True)
class BuildJob:
    recipe: Recipe
    python: PythonVersion

    @property
    def ref(self) -> str:
        return self.recipe.ref
