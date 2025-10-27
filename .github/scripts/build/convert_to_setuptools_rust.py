import os
import sys
from pathlib import Path
import tomli
import tomli_w

def normalize_pyproject_toml_for_pep621(pyproject: dict):
    """Normalizes the pyproject.toml to comply with modern PEP standards for setuptools."""
    project_table = pyproject.get("project", {})

    # PEP 621: Move `repository` from [project] to [project.urls]
    if "repository" in project_table:
        repo_url = project_table["repository"]
        del project_table["repository"]
        if "urls" not in project_table:
            project_table["urls"] = {}
        project_table["urls"]["Repository"] = repo_url
        print("Normalized 'repository' field for PEP 621 compliance.")

    # PEP 639: If a license expression is used, remove legacy license classifiers
    if "license" in project_table and "classifiers" in project_table:
        original_classifiers = project_table["classifiers"]
        project_table["classifiers"] = [
            c for c in original_classifiers if not c.startswith("License ::")
        ]
        if len(original_classifiers) > len(project_table["classifiers"]):
            print("Removed legacy 'License ::' classifiers for PEP 639 compliance.")

def normalize_cargo_toml_for_setuptools_rust(cargo_path: Path):
    """Ensures Cargo.toml is compatible with setuptools-rust's default behavior."""
    print(f"Normalizing Cargo.toml at: {cargo_path}")
    with open(cargo_path, "rb") as f:
        cargo_toml = tomli.load(f)

    dependencies = cargo_toml.get("dependencies", {})
    has_direct_pyo3 = "pyo3" in dependencies
    has_pyo3_ffi = "pyo3-ffi" in dependencies

    # If the project uses pyo3-ffi but not pyo3 directly (e.g., orjson),
    # we need to add a feature-bearing pyo3 dependency for setuptools-rust
    # to latch onto.
    if has_pyo3_ffi and not has_direct_pyo3:
        print("Project uses 'pyo3-ffi' without a direct 'pyo3' dependency.")
        print("Adding a feature-only 'pyo3' dependency to Cargo.toml.")
        
        pyo3_ffi_dep = dependencies["pyo3-ffi"]
        pyo3_version = ""
        if isinstance(pyo3_ffi_dep, dict) and "version" in pyo3_ffi_dep:
            pyo3_version = pyo3_ffi_dep["version"]
        elif isinstance(pyo3_ffi_dep, str):
             pyo3_version = pyo3_ffi_dep

        if not pyo3_version:
            print("Warning: Could not determine version for pyo3-ffi, cannot add pyo3 dependency.", file=sys.stderr)
            return

        # Add a pyo3 dependency that carries the feature, but doesn't enable default features
        cargo_toml["dependencies"]["pyo3"] = {
            "version": pyo3_version,
            "default-features": False,
            "features": ["extension-module"]
        }

        # Remove the 'extension-module' feature from pyo3-ffi to avoid conflicts
        if isinstance(pyo3_ffi_dep, dict) and "features" in pyo3_ffi_dep:
            pyo3_ffi_dep["features"] = [
                f for f in pyo3_ffi_dep["features"] if f != "extension-module"
            ]
            print("Removed 'extension-module' feature from 'pyo3-ffi' dependency.")

        with open(cargo_path, "wb") as f:
            tomli_w.dump(cargo_toml, f)
            print("Successfully wrote updated Cargo.toml.")

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

    print(f"---")
    print(f"Converting project at: {project_path}")

    # Step 1: Normalize pyproject.toml for PEP compliance
    normalize_pyproject_toml_for_pep621(pyproject)
    
    # Step 2: Normalize Cargo.toml for setuptools-rust compatibility
    normalize_cargo_toml_for_setuptools_rust(cargo_path)

    maturin_config = pyproject.get("tool", {}).get("maturin", {})
    package_name, source_dir = find_python_package_info(project_path, pyproject)
    print(f"Found Python package '{package_name}' in source directory '{source_dir}'")

    with open(cargo_path, "rb") as f:
        cargo_toml = tomli.load(f)
    crate_name = cargo_toml.get("lib", {}).get("name")
    if not crate_name:
        raise ValueError("Could not find [lib].name in Cargo.toml")
    print(f"Found Rust crate name: '{crate_name}'")

    # Step 3: Remove [tool.maturin]
    if "maturin" in pyproject.get("tool", {}):
        del pyproject["tool"]["maturin"]
        print("Removed [tool.maturin] section.")

    # Step 4: Update [build-system]
    pyproject["build-system"]["requires"] = ["setuptools", "setuptools-rust"]
    pyproject["build-system"]["build-backend"] = "setuptools.build_meta"
    print("Updated [build-system] for setuptools-rust.")

    # Step 5: Handle dynamic fields in pyproject.toml
    if "dynamic" in pyproject.get("project", {}):
        if "tool" not in pyproject:
            pyproject["tool"] = {}
        if "setuptools" not in pyproject["tool"]:
            pyproject["tool"]["setuptools"] = {}
        if "dynamic" not in pyproject["tool"]["setuptools"]:
            pyproject["tool"]["setuptools"]["dynamic"] = {}

        for field in pyproject["project"]["dynamic"]:
            if field == "readme":
                pyproject["tool"]["setuptools"]["dynamic"]["readme"] = {
                    "file": ["README.md"],
                    "content-type": "text/markdown"
                }
                print(f"Added [tool.setuptools.dynamic.readme] for README.md")
            elif field == "version":
                print("Found dynamic version, will be handled by setuptools-rust automatically.")

    # Step 6: Add [tool.setuptools.packages.find] for multi-module projects
    if source_dir != ".":
        if "tool" not in pyproject:
            pyproject["tool"] = {}
        if "setuptools" not in pyproject["tool"]:
            pyproject["tool"]["setuptools"] = {}
        pyproject["tool"]["setuptools"]["packages"] = {"find": {"where": [source_dir]}}
        print(f"Added [tool.setuptools.packages.find] with where=['{source_dir}'].")

    # Step 7: Add [[tool.setuptools-rust.ext-modules]]
    if "module-name" in maturin_config:
        target = maturin_config["module-name"]
    elif source_dir == ".":
        target = crate_name
    else:
        target = f"{package_name}.{crate_name}"

    # We no longer add `features = []` here, allowing setuptools-rust to use its default behavior,
    # because we have normalized Cargo.toml to be compatible.
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