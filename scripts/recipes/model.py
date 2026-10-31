"""Represent recipe data and explicit build selections."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.build.build_tools import BuildTool
from scripts.build.native_model import NativeLibrary

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
    AIO_LIBS = "pep517_backend.hooks"
    MESON = "mesonpy"
    HATCHLING = "hatchling.build"
    SETUPTOOLS_LEGACY = "setuptools.build_meta:__legacy__"
    PILLOW = "backend"
    SCIKIT_BUILD = "scikit_build_core.build"
    DUCKDB = "duckdb_packaging.build_backend"


class Publication(StrEnum):
    PUBLISH = "publish"
    BUILD = "build"


@dataclass(frozen=True)
class Android:
    python: Choices[PythonVersion]
    abis: Choices[AndroidABI]
    api: int


@dataclass(frozen=True)
class GitLocation:
    repository: str
    ref: str


@dataclass(frozen=True)
class PyPILocation:
    package: str
    version: str


Location = GitLocation | PyPILocation
L = TypeVar("L", GitLocation, PyPILocation)


@dataclass(frozen=True)
class EnvironmentVariable:
    name: str
    value: str


@dataclass(frozen=True)
class ConfigSetting:
    name: str
    value: str


@dataclass(frozen=True)
class Recipe(Generic[L]):
    name: str
    source: L
    directory: str
    backend: Backend
    android: Android
    environment: tuple[EnvironmentVariable, ...] = ()
    native_dependencies: tuple[NativeLibrary, ...] = ()
    config_settings: tuple[ConfigSetting, ...] = ()
    build_tools: tuple[BuildTool, ...] = ()


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
    recipe: Recipe[GitLocation]
    ref: str
    python: PythonSelection = RecipePython()


BuildSelection = RecipeBuilds | RefBuild


@dataclass(frozen=True)
class BuildJob:
    recipe: Recipe
    python: PythonVersion
