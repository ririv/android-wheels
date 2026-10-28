"""Validate recipe configuration at the command-line boundary."""

import argparse
from pathlib import Path

from scripts.recipes.load import load_recipes


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--recipes-dir", type=Path, default=Path("recipes"))
    args = parser.parse_args()
    print(f"已校验 {len(load_recipes(args.recipes_dir))} 个 recipe")


if __name__ == "__main__":
    main()
