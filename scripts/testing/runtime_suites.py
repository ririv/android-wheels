"""Declare composable Android runtime suites and artifact layouts."""

from dataclasses import dataclass
from enum import StrEnum


class RuntimeSuite(StrEnum):
    PLOTTING = "plotting"
    DATA = "data"
    NUMERICAL = "numerical"
    LEARNING = "learning"
    ANALYTICS = "analytics"


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
    RuntimeSuite.LEARNING: Suite(
        ("scikit-learn",),
        "scikit-learn",
        ("numpy", "scipy"),
        "learning-pure-dependencies.json",
        "learning_smoke.py",
    ),
    RuntimeSuite.ANALYTICS: Suite(
        ("pyarrow", "psycopg2-binary"),
        "psycopg2-binary",
        ("numpy", "pandas"),
        "analytics-pure-dependencies.json",
        "analytics_smoke.py",
    ),
    RuntimeSuite.NUMERICAL: Suite(
        ("scipy",),
        "scipy",
        ("numpy",),
        "numerical-pure-dependencies.json",
        "scipy_smoke.py",
    ),
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
