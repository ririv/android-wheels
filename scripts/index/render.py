"""Render deterministic HTML using explicitly provided wheel metadata."""

import html
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

from scripts.index.metadata import Wheel


def render(wheels: tuple[Wheel, ...], repository: str, output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"索引输出目录必须不存在：{output}")
    output.mkdir(parents=True)
    packages = defaultdict(list)
    for wheel in wheels:
        name = re.sub(r"[-_.]+", "-", wheel.path.name.split("-")[0]).lower()
        packages[name].append(wheel)
    rows = []
    for name, files in sorted(packages.items()):
        date = max(wheel.modified for wheel in files)
        rows.append(
            f'<tr><td><a href="{name}/">{name}</a></td><td>{date:%Y-%m-%d %H:%M:%S %Z}</td></tr>'
        )
        directory = output / name
        directory.mkdir()
        links = []
        for wheel in sorted(files, key=lambda item: item.path.name):
            url = f"https://github.com/{repository}/raw/wheels/{quote(wheel.path.as_posix())}"
            links.append(
                f'<tr><td><a href="{html.escape(url, quote=True)}">{html.escape(wheel.path.name)}</a></td><td>{wheel.modified:%Y-%m-%d %H:%M:%S %Z}</td></tr>'
            )
        (directory / "index.html").write_text(document(name, links), encoding="utf-8")
    (output / "index.html").write_text(
        document("Py Extra Wheels", rows), encoding="utf-8"
    )


def document(title: str, rows: list[str]) -> str:
    return (
        '<!DOCTYPE html>\n<html><head><meta charset="utf-8"><title>'
        + html.escape(title)
        + "</title></head>\n<body><table>\n"
        + "\n".join(rows)
        + "\n</table></body></html>\n"
    )
