"""Read wheel paths and modification dates with two batch Git queries."""

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class Wheel:
    path: PurePosixPath
    modified: datetime


def read_wheels(checkout: Path) -> tuple[Wheel, ...]:
    paths = (
        subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "-z", "HEAD"], cwd=checkout
        )
        .decode()
        .split("\0")
    )
    wheels = sorted(path for path in paths if path.endswith(".whl"))
    if not wheels:
        raise ValueError("wheels 分支没有 wheel，拒绝发布空索引")
    history = subprocess.check_output(
        [
            "git",
            "log",
            "--format=@@%ct",
            "--name-only",
            "--no-renames",
            "--full-history",
            "-m",
            "HEAD",
            "--",
            "*.whl",
        ],
        cwd=checkout,
        text=True,
    )
    dates = {}
    for line in history.splitlines():
        if line.startswith("@@"):
            date = datetime.fromtimestamp(int(line[2:]), tz=UTC)
        elif line:
            dates.setdefault(line, date)
    return tuple(Wheel(PurePosixPath(path), dates[path]) for path in wheels)
