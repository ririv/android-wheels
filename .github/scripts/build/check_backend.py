#!/usr/bin/env python3

import sys
from pathlib import Path

def get_build_backend(project_path: Path) -> str:
    """Reads pyproject.toml and returns the build backend."""
    # 递归查找pyproject.toml文件
    pyproject_files = list(project_path.rglob("pyproject.toml"))

    if not pyproject_files:
        # 如果没有找到pyproject.toml，查找setup.py
        setup_files = list(project_path.rglob("setup.py"))
        if not setup_files:
            print("No pyproject.toml or setup.py found, assuming setuptools", file=sys.stderr)
            return "setuptools"
        # 使用setup.py的目录
        pyproject_path = setup_files[0]
        print(f"Found setup.py at: {pyproject_path}", file=sys.stderr)
        return "setuptools"

    # 使用找到的第一个pyproject.toml文件
    pyproject_path = pyproject_files[0]
    print(f"Found pyproject.toml at: {pyproject_path}", file=sys.stderr)

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
