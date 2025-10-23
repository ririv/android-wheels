import subprocess
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

    content = cargo_toml_path.read_text(encoding="utf-8")
    # A simple string replacement is used here to avoid re-writing the entire file
    # and potentially breaking formatting or comments. This is brittle but effective
    # for the known structure of jiter's Cargo.toml.
    original_pyo3_dep = 'pyo3 = { version = "0.26.0" }'
    patched_pyo3_dep = 'pyo3 = { version = "0.26.0", features = ["extension-module"] }'

    if original_pyo3_dep in content:
        new_content = content.replace(original_pyo3_dep, patched_pyo3_dep)
        cargo_toml_path.write_text(new_content, encoding="utf-8")
        print("Successfully patched pyo3 dependency to include 'extension-module'.")
    else:
        print("WARNING: pyo3 dependency line not found in expected format, skipping patch.")

def patch_orjson_for_android(project_path: Path):
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
        ok2 = '''#[cfg(any(target_arch = "x86", target_arch = "x86_64"))]''' in pystr.read_text(encoding="utf-8")

    if not (ok1 and ok2):
        print("WARNING: orjson patch verification failed (one of the guards missing). Build may fail on aarch64.")
