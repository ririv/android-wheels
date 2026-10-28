"""Load and strictly validate recipe TOML files."""

import re
import tomllib
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import TypeVar

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.recipes.model import (
    Android,
    Backend,
    Choices,
    GitLocation,
    LiteralEnvironment,
    PyPILocation,
    Recipe,
    TargetEnvironment,
    TargetField,
)

T = TypeVar("T")
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
GIT_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./+\-]*")


def choices(values: list, convert: Callable[[str], T], label: str) -> Choices[T]:
    if (
        not isinstance(values, list)
        or not values
        or any(type(v) is not str for v in values)
    ):
        raise ValueError(f"{label} 必须是非空字符串数组")
    converted = tuple(convert(v) for v in values)
    if len(set(converted)) != len(converted):
        raise ValueError(f"{label} 存在重复项")
    return Choices(converted[0], converted[1:])


def validate_ref(value: str) -> str:
    if not GIT_REF.fullmatch(value) or ".." in value or "@{" in value:
        raise ValueError(f"无效的 Git ref：{value!r}")
    return value


def require_keys(data: dict, expected: set[str], label: str) -> None:
    if not isinstance(data, dict) or set(data) != expected:
        raise ValueError(f"{label} 字段必须恰好为：{', '.join(sorted(expected))}")


def load_recipe(path: Path) -> Recipe:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    common = {"name", "directory", "backend", "android"}
    if "environment" in data:
        common.add("environment")
    if "pypi-version" in data:
        require_keys(data, common | {"pypi-version"}, str(path))
        if type(data["pypi-version"]) is not str or not data["pypi-version"]:
            raise ValueError("pypi-version 必须显式指定发行版本")
        source = PyPILocation(data["name"], data["pypi-version"])
    else:
        require_keys(data, common | {"repository", "ref"}, str(path))
        if type(data["repository"]) is not str or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", data["repository"]
        ):
            raise ValueError(f"{path}: repository 必须是 GitHub owner/repo")
        if type(data["ref"]) is not str:
            raise ValueError("Git ref 必须是字符串")
        source = GitLocation(data["repository"], validate_ref(data["ref"]))
    for key in ["name", "directory", "backend"]:
        if type(data[key]) is not str or not data[key]:
            raise ValueError(f"{path}: {key} 必须是非空字符串")
    if not NAME.fullmatch(data["name"]) or path.stem != data["name"]:
        raise ValueError(f"{path}: 包名必须规范化且与文件名相同")
    directory = PurePosixPath(data["directory"])
    if directory.is_absolute() or ".." in directory.parts or "\\" in data["directory"]:
        raise ValueError(f"{path}: directory 必须在源码仓库内")
    android = data["android"]
    require_keys(android, {"python", "abis", "api"}, f"{path}: android")
    if type(android["api"]) is not int or android["api"] < 24:
        raise ValueError(f"{path}: Android API 必须是至少为 24 的整数")
    return Recipe(
        name=data["name"],
        source=source,
        directory=directory.as_posix(),
        backend=Backend(data["backend"]),
        android=Android(
            python=choices(android["python"], PythonVersion, "android.python"),
            abis=choices(android["abis"], AndroidABI, "android.abis"),
            api=android["api"],
        ),
        environment=environment(data.get("environment", {})),
    )


def environment(data: dict) -> tuple:
    if not isinstance(data, dict):
        raise ValueError("environment 必须是变量表")
    result = []
    framework = {
        "LIBRARY_NAME",
        "PROJECT_DIR",
        "TARGET_PYTHON_VERSION",
        "ANDROID_API",
        "TARGET_ABI",
        "ARTIFACT",
        "WHEEL_DIRECTORY",
        "HOST_PYTHON",
        "RUNNER_TEMP",
    }
    reserved = {
        "PATH",
        "CC",
        "CXX",
        "AR",
        "CFLAGS",
        "CXXFLAGS",
        "LDFLAGS",
        "ANDROID_API_LEVEL",
        "PYO3_CROSS",
        "PYO3_CONFIG_FILE",
        "PYO3_CROSS_LIB_DIR",
        "PYO3_CROSS_PYTHON_VERSION",
        "CARGO_BUILD_TARGET",
    }
    for name, value in sorted(data.items()):
        if (
            not re.fullmatch(r"[A-Z][A-Z0-9_]*", name)
            or name in reserved | framework
            or name.startswith(("CIBW_", "CARGO_TARGET_", "GITHUB_"))
        ):
            raise ValueError(f"不允许覆盖构建器变量：{name}")
        match value:
            case str(text) if not any(char in text for char in "\n\r\0"):
                result.append(LiteralEnvironment(name, text))
            case {"target": str(field)} if set(value) == {"target"}:
                result.append(TargetEnvironment(name, TargetField(field)))
            case _:
                raise ValueError(f"{name} 必须是单行字符串或明确的目标字段引用")
    return tuple(result)


def load_recipes(directory: Path) -> tuple[Recipe, ...]:
    recipes = tuple(load_recipe(path) for path in sorted(directory.glob("*.toml")))
    if not recipes:
        raise ValueError(f"没有找到 recipe：{directory}")
    return recipes
