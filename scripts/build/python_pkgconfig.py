"""Expose the selected Android CPython prefix to pkg-config consumers."""

from pathlib import Path

from scripts.build.android_python import PYTHON_ARCHIVES, PythonVersion


def write_python_pkgconfig(prefix: Path, version: PythonVersion) -> None:
    directory = prefix / "lib/pkgconfig"
    directory.mkdir(parents=True, exist_ok=True)
    release = PYTHON_ARCHIVES[version].release.partition("-")[0]
    escaped = str(prefix).replace("\\", "\\\\").replace(" ", "\\ ")
    content = (
        f"prefix={escaped}\n"
        "libdir=${prefix}/lib\n"
        f"includedir=${{prefix}}/include/python{version}\n\n"
        "Name: Python\n"
        "Description: Android CPython development files\n"
        f"Version: {release}\n"
        f"Libs: -L${{libdir}} -lpython{version}\n"
        "Cflags: -I${includedir}\n"
    )
    for name in ("python3", f"python-{version}"):
        (directory / f"{name}.pc").write_text(content)
