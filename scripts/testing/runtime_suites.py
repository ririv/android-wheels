"""Declare composable Android runtime suites and artifact layouts."""

from dataclasses import dataclass
from enum import StrEnum


class RuntimeSuite(StrEnum):
    PLOTTING = "plotting"
    DATA = "data"


class ArtifactLayout(StrEnum):
    BUILD = "build"
    REPACKAGED = "repackaged"


@dataclass(frozen=True)
class Suite:
    packages: tuple[str, ...]
    entry: str
    published: tuple[str, ...]
    pure_lock: str
    script: str


SUITES = {
    RuntimeSuite.PLOTTING: Suite(
        ("contourpy", "pandas", "matplotlib"),
        "matplotlib",
        ("numpy", "pillow", "fonttools", "kiwisolver"),
        "scientific-pure-dependencies.json",
        "scientific_smoke.py",
    ),
    RuntimeSuite.DATA: Suite(
        ("shapely", "duckdb", "polars-runtime-32", "thrift"),
        "shapely",
        ("numpy", "pandas"),
        "data-pure-dependencies.json",
        "data_smoke.py",
    ),
}
