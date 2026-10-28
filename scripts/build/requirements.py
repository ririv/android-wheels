"""Expose the selected project's declared PEP 517 host build requirements."""

import argparse
import tomllib
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = tomllib.loads(
        (args.project / "pyproject.toml").read_text(encoding="utf-8")
    )
    requirements = project["build-system"]["requires"]
    if not isinstance(requirements, list) or any(
        type(item) is not str or any(char in item for char in "\n\r\0")
        for item in requirements
    ):
        raise ValueError("build-system.requires 必须是单行 PEP 508 字符串数组")
    args.output.write_text("\n".join(requirements) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
