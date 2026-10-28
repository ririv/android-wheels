"""Read pinned tool settings and dependency groups from one project configuration."""

import argparse
import tomllib
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def configuration() -> dict:
    return tomllib.loads(PROJECT.read_text(encoding="utf-8"))


def settings() -> dict:
    return configuration()["tool"]["py-extra-wheels"]


def requirements(
    group: str, groups: dict, visiting: tuple[str, ...] = ()
) -> tuple[str, ...]:
    if group in visiting:
        raise ValueError(f"依赖组存在循环：{(*visiting, group)}")
    result = []
    for item in groups[group]:
        match item:
            case str(package):
                result.append(package)
            case {"include-group": str(name)}:
                result.extend(requirements(name, groups, (*visiting, group)))
            case _:
                raise ValueError(f"无效依赖组条目：{item}")
    return tuple(dict.fromkeys(result))


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    output = commands.add_parser("outputs")
    output.add_argument("--github-output", type=Path, required=True)
    dependencies = commands.add_parser("requirements")
    dependencies.add_argument("group", choices=["toml", "shared", "build"])
    dependencies.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "outputs":
        with args.github_output.open("a", encoding="utf-8") as stream:
            for name, value in settings().items():
                stream.write(f"{name.replace('-', '_')}={value}\n")
    else:
        args.output.write_text(
            "\n".join(requirements(args.group, configuration()["dependency-groups"]))
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
