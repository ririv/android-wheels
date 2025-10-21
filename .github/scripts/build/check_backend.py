#!/usr/bin/env python3

import sys
from pathlib import Path

def get_build_backend(project_path: Path) -> str:
    """Reads pyproject.toml and returns the build backend."""
    pyproject_path = project_path / "pyproject.toml"
    if not pyproject_path.is_file():
        # Assume setuptools for projects without pyproject.toml (e.g., legacy setup.py)
        return "setuptools"

    try:
        import tomllib
    except ImportError:
        # This script runs in a controlled environment (Python 3.11+),
        # so this should ideally not happen.
        import tomli as tomllib

    pyproject_content = tomllib.loads(pyproject_path.read_text())
    build_system = pyproject_content.get("build-system", {})
    backend = build_system.get("build-backend", "setuptools") # Default to setuptools
    
    return backend

def main():
    if len(sys.argv) != 2:
        print("Usage: python check_backend.py <project_path>", file=sys.stderr)
        sys.exit(1)

    project_path = Path(sys.argv[1])
    backend = get_build_backend(project_path)
    print(backend)

if __name__ == "__main__":
    main()
