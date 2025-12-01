import os
import sys
from pathlib import Path
import tomllib
import tomli_w

def set_github_actions_env_variable(name: str, value: str):
    """Sets an environment variable for subsequent steps in a GitHub Actions job."""
    github_env = os.getenv("GITHUB_ENV")
    if github_env:
        with open(github_env, "a") as f:
            f.write(f"{name}={value}\n")
        print(f"Successfully set environment variable: {name}={value}")
    else:
        print(f"Warning: GITHUB_ENV not found. Cannot set environment variable {name}.", file=sys.stderr)
        print(f"Would set {name}={value}")

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
        cargo_toml = tomllib.load(f)

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

def get_cargo_version(cargo_path: Path) -> str | None:
    """Gets the version from a Cargo.toml, supporting workspaces."""
    with open(cargo_path, "rb") as f:
        cargo_toml = tomllib.load(f)

    package_table = cargo_toml.get("package", {})
    version_field = package_table.get("version")

    # 1. Check if the version field is a direct version string
    if isinstance(version_field, str):
        return version_field
    
    # 2. Check if the version field is a workspace reference
    if isinstance(version_field, dict) and version_field.get("workspace") is True:
        print("Version is in workspace. Searching for root Cargo.toml...")
        current_dir = cargo_path.parent
        # Search upwards for a Cargo.toml that defines the workspace
        while current_dir != current_dir.parent:
            root_cargo_path = current_dir / "Cargo.toml"
            if root_cargo_path.is_file():
                with open(root_cargo_path, "rb") as rf:
                    root_cargo_toml = tomllib.load(rf)
                if "workspace" in root_cargo_toml:
                    workspace_version = root_cargo_toml.get("workspace", {}).get("package", {}).get("version")
                    if workspace_version:
                        print(f"Found workspace version {workspace_version} in {root_cargo_path}")
                        return workspace_version
            current_dir = current_dir.parent
            
    # 3. If neither is found, return None
    return None

def convert_project(pyproject_path: Path):
    """Converts a single project defined by a pyproject.toml file."""
    project_path = pyproject_path.parent
    cargo_path = project_path / "Cargo.toml"

    if not cargo_path.is_file():
        print(f"Warning: Cargo.toml not found in {project_path}, skipping conversion for {pyproject_path}", file=sys.stderr)
        return

    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    if pyproject.get("build-system", {}).get("build-backend") != "maturin":
        print(f"Project at {project_path} is not using maturin. No conversion needed.", file=sys.stderr)
        return

    print(f"---")
    print(f"Converting project at: {project_path}")

    # Step 1: Handle dynamic version before any conversion
    if "version" in pyproject.get("project", {}).get("dynamic", []):
        print("Dynamic version detected. Setting SETUPTOOLS_SCM_PRETEND_VERSION from Cargo.toml...")
        cargo_version = get_cargo_version(cargo_path)
        if cargo_version:
            set_github_actions_env_variable("SETUPTOOLS_SCM_PRETEND_VERSION", cargo_version)
        else:
            print("Warning: Could not find version in Cargo.toml to set environment variable.", file=sys.stderr)

    # Step 2: Normalize pyproject.toml for PEP compliance
    normalize_pyproject_toml_for_pep621(pyproject)
    
    # Step 3: Normalize Cargo.toml for setuptools-rust compatibility
    normalize_cargo_toml_for_setuptools_rust(cargo_path)

    maturin_config = pyproject.get("tool", {}).get("maturin", {})
    package_name, source_dir = find_python_package_info(project_path, pyproject)
    print(f"Found Python package '{package_name}' in source directory '{source_dir}'")

    with open(cargo_path, "rb") as f:
        cargo_toml = tomllib.load(f)
    crate_name = cargo_toml.get("lib", {}).get("name")
    if not crate_name:
        raise ValueError("Could not find [lib].name in Cargo.toml")
    print(f"Found Rust crate name: '{crate_name}'")

    # Step 4: Remove [tool.maturin]
    if "maturin" in pyproject.get("tool", {}):
        del pyproject["tool"]["maturin"]
        print("Removed [tool.maturin] section.")

    # Step 5: Update [build-system]
    pyproject["build-system"]["requires"] = ["setuptools", "setuptools-rust", "setuptools_scm[simple]"]
    pyproject["build-system"]["build-backend"] = "setuptools.build_meta"
    print("Updated [build-system] for setuptools-rust and setuptools_scm.")

    # Step 6: Handle dynamic fields in pyproject.toml
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

    # Step 7: Add [tool.setuptools.packages.find] for multi-module projects
    if source_dir != ".":
        if "tool" not in pyproject:
            pyproject["tool"] = {}
        if "setuptools" not in pyproject["tool"]:
            pyproject["tool"]["setuptools"] = {}
        pyproject["tool"]["setuptools"]["packages"] = {"find": {"where": [source_dir]}}
        print(f"Added [tool.setuptools.packages.find] with where=['{source_dir}'].")

    # Step 8: Add [[tool.setuptools-rust.ext-modules]]
    if "module-name" in maturin_config:
        target = maturin_config["module-name"]
    elif source_dir == ".":
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