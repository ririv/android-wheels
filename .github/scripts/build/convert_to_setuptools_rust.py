import os
import sys
from pathlib import Path
import tomli
import tomli_w

def find_python_package_info(project_path: Path, pyproject: dict) -> tuple[str, str]:
    """
    Finds the Python package name and source directory.
    Returns a tuple of (package_name, source_directory).
    """
    maturin_config = pyproject.get("tool", {}).get("maturin", {})

    if "python-source" in maturin_config:
        source_dir = maturin_config["python-source"]
        pysrc_path = project_path / source_dir
        packages = [p.name for p in pysrc_path.iterdir() if p.is_dir() and (p / "__init__.py").exists()]
        if packages:
            return packages[0], source_dir
    
    # If no python-source, assume the package is at the root
    project_name = pyproject.get("project", {}).get("name")
    if project_name:
        return project_name, "."

    raise FileNotFoundError("Could not find Python package information.")

def convert_project(pyproject_path: Path):
    """Converts a single project defined by a pyproject.toml file."""
    project_path = pyproject_path.parent
    cargo_path = project_path / "Cargo.toml"

    if not cargo_path.is_file():
        print(f"Warning: Cargo.toml not found in {project_path}, skipping conversion for {pyproject_path}", file=sys.stderr)
        return

    with open(pyproject_path, "rb") as f:
        pyproject = tomli.load(f)

    if pyproject.get("build-system", {}).get("build-backend") != "maturin":
        print(f"Project at {project_path} is not using maturin. No conversion needed.", file=sys.stderr)
        return

    # --- Start Conversion ---
    print(f"---")
    print(f"Converting project at: {project_path}")

    # Find Python package info
    package_name, source_dir = find_python_package_info(project_path, pyproject)
    print(f"Found Python package '{package_name}' in source directory '{source_dir}'")

    # Get Rust crate name from Cargo.toml
    with open(cargo_path, "rb") as f:
        cargo_toml = tomli.load(f)
    crate_name = cargo_toml.get("lib", {}).get("name")
    if not crate_name:
        raise ValueError("Could not find [lib].name in Cargo.toml")
    print(f"Found Rust crate name: '{crate_name}'")

    # 1. Remove [tool.maturin]
    if "maturin" in pyproject.get("tool", {}):
        del pyproject["tool"]["maturin"]
        print("Removed [tool.maturin] section.")

    # 2. Update [build-system]
    pyproject["build-system"]["requires"] = ["setuptools", "setuptools-rust"]
    pyproject["build-system"]["build-backend"] = "setuptools.build_meta"
    print("Updated [build-system] for setuptools-rust.")

    # 3. Add [tool.setuptools.packages.find] for multi-module projects
    if source_dir != ".":
        if "tool" not in pyproject:
            pyproject["tool"] = {}
        if "setuptools" not in pyproject["tool"]:
            pyproject["tool"]["setuptools"] = {}
        pyproject["tool"]["setuptools"]["packages"] = {"find": {"where": [source_dir]}}
        print(f"Added [tool.setuptools.packages.find] with where=['{source_dir}'].")

    # 4. Add [[tool.setuptools-rust.ext-modules]]
    if source_dir == ".":
        target = crate_name
    else:
        target = f"{package_name}.{crate_name}"

    ext_module = {
        "target": target,
        "path": "Cargo.toml",
        "binding": "PyO3"
    }
    if "tool" not in pyproject:
        pyproject["tool"] = {}
    if "setuptools-rust" not in pyproject["tool"]:
        pyproject["tool"]["setuptools-rust"] = {}
    pyproject["tool"]["setuptools-rust"]["ext-modules"] = [ext_module]
    print(f"Added [[tool.setuptools-rust.ext-modules]] with target '{ext_module['target']}'.")

    # Write back the modified pyproject.toml
    with open(pyproject_path, "wb") as f:
        tomli_w.dump(pyproject, f)

    print(f"Successfully updated {pyproject_path}")


def main():
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <project_path>", file=sys.stderr)
        sys.exit(1)

    project_path = Path(sys.argv[1]).resolve()
    
    pyproject_files = list(project_path.rglob("pyproject.toml"))

    if not pyproject_files:
        print(f"Error: No pyproject.toml found in {project_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(pyproject_files)} pyproject.toml file(s). Converting...")

    for pyproject_path in pyproject_files:
        convert_project(pyproject_path)

    print("\nConversion complete!")

if __name__ == "__main__":
    main()
