import subprocess
import tomllib
import tomli_w
from pathlib import Path

def run(cmd, **kwargs):
    print(f"$ {' '.join(map(str, cmd))}")
    return subprocess.run(cmd, check=True, **kwargs)

def which(cmd: str) -> bool:
    from shutil import which as _which
    return _which(cmd) is not None

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

def patch_orjson_for_android(project_path: Path) -> None:
    """
    在非 x86 目标上为 orjson 打最小补丁，避免编译 x86/AVX 代码：
    1) 给 src/str/avx512.rs 整文件加 x86/x86_64 cfg 守卫；
    2) 给 src/str/pystr.rs 中 is_x86_feature_detected! 调用加 cfg 守卫。
    """
    print("--- Patching orjson sources for non-x86 targets ---")
    str_dir = project_path / "src" / "str"
    avx512 = str_dir / "avx512.rs"
    pystr = str_dir / "pystr.rs"

    ok1 = ok2 = False

    if avx512.exists():
        txt = avx512.read_text(encoding="utf-8")
        guard = '''#![cfg(any(target_arch = "x86", target_arch = "x86_64"))]'''
        if guard not in txt:
            avx512.write_text(guard + "\n" + txt, encoding="utf-8")
            print("Injected cfg guard into orjson/src/str/avx512.rs")
        ok1 = guard in avx512.read_text(encoding="utf-8")

    if pystr.exists():
        txt = pystr.read_text(encoding="utf-8")
        patched = txt
        # avx512 检测
        patched = patched.replace(
            '''if std::is_x86_feature_detected!(\"avx512vl\") {''',
            '''#[cfg(any(target_arch = \"x86\", target_arch = \"x86_64\"))]\n        if std::is_x86_feature_detected!(\"avx512vl\") {'''
        )
        # 若还有 avx2 检测，一并守卫（不存在也无影响）
        patched = patched.replace(
            '''if std::is_x86_feature_detected!(\"avx2\") {''',
            '''#[cfg(any(target_arch = \"x86\", target_arch = \"x86_64\"))]\n        if std::is_x86_feature_detected!(\"avx2\") {'''
        )
        if patched != txt:
            pystr.write_text(patched, encoding="utf-8")
            print("Injected cfg guards into orjson/src/str/pystr.rs")
        ok2 = '''#[cfg(any(target_arch = \"x86\", target_arch = \"x86_64\"))]''' in pystr.read_text(encoding="utf-8")

    if not (ok1 and ok2):
        print("WARNING: orjson patch verification failed (one of the guards missing). Build may fail on aarch64.")


def create_cargo_config(project_path: Path, target_triplet: str, android_api: str):
    """Creates a .cargo/config.toml file to configure the build."""
    print("--- Creating .cargo/config.toml for cross-compilation ---")
    cargo_dir = project_path / ".cargo"
    cargo_dir.mkdir(exist_ok=True)

    linker_name = f"{target_triplet}{android_api}-clang"

    config_data = {
        "target": {
            target_triplet: {
                "linker": linker_name
            }
        }
    }

    config_path = cargo_dir / "config.toml"
    with open(config_path, "wb") as f:
        tomli_w.dump(config_data, f)
    
    print(f"Created {config_path} with linker set to {linker_name}")