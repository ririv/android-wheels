import os
import sys
import subprocess
import tomllib
import tomli_w
from pathlib import Path



def patch_pyo3_cargo_toml(project_path: Path):
    """Patches the project's Cargo.toml to add `extension-module` feature to pyo3."""
    print("--- Patching Cargo.toml for pyo3 extension-module ---")
    cargo_toml_path = project_path / "Cargo.toml"
    if not cargo_toml_path.is_file():
        print(f"WARNING: Cargo.toml not found at {cargo_toml_path}, skipping patch.")
        return

    with open(cargo_toml_path, "rb") as f:
        data = tomllib.load(f)

    dependencies = data.get("dependencies", {})
    pyo3_dep = dependencies.get("pyo3")

    if not pyo3_dep:
        print("WARNING: pyo3 dependency not found, skipping patch.")
        return

    # If pyo3 is just a version string, convert it to a table
    if isinstance(pyo3_dep, str):
        pyo3_dep = {"version": pyo3_dep}
        dependencies["pyo3"] = pyo3_dep

    if not isinstance(pyo3_dep, dict):
        print(f"WARNING: pyo3 dependency has unsupported format ({type(pyo3_dep)}), skipping patch.")
        return

    features = pyo3_dep.get("features", [])
    if "extension-module" not in features:
        features.append("extension-module")
        pyo3_dep["features"] = features
        
        with open(cargo_toml_path, "wb") as f:
            tomli_w.dump(data, f)
        print("Successfully patched pyo3 dependency to include 'extension-module'.")
    else:
        print("pyo3 dependency already includes 'extension-module'.")

def create_cargo_config(project_path: Path, target_triplet: str, android_api: str, python_lib_dir: Path, python_version: str):
    """Creates a .cargo/config.toml file to configure the build."""
    print("--- Creating .cargo/config.toml for cross-compilation ---")
    cargo_dir = project_path / ".cargo"
    cargo_dir.mkdir(exist_ok=True)

    linker_name = os.environ.get("CC", '')
    ar_name = os.environ.get("AR", '')

    print(f"Using linker {linker_name} and ar {ar_name}")

    # Correctly configure rustflags to point to the python library
    # This is more robust than environment variables as it's read directly by cargo.
    config_data = {
        "target": {
            target_triplet: {
                "linker": linker_name,
                "ar": ar_name,
            }
        }
    }

    # config_data["rustflags"] = [
    #     "-L",
    #     str(python_lib_dir),
    #     "-Wl,-rpath,{}".format(python_lib_dir),
    #     "-Wl,--as-needed",
    #     "-Wl,--no-undefined",
    #     "-Wl,--exclude-libs,ALL",
    #     "-Wl,-Bsymbolic-functions",
    #     "-Wl,-z,relro",
    # ]

    config_path = cargo_dir / "config.toml"
    with open(config_path, "wb") as f:
        tomli_w.dump(config_data, f)
    
    print(f"Created {config_path} with linker and direct rustflags for python lib.")