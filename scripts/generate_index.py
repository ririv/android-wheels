"""Generate the wheel index from an explicit repository checkout."""

import argparse
from pathlib import Path

from scripts.build.normalize_repo_input import normalize_repo_input
from scripts.index.metadata import read_wheels
from scripts.index.render import render


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--repository", type=normalize_repo_input, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(read_wheels(args.checkout), args.repository, args.output)


if __name__ == "__main__":
    main()
