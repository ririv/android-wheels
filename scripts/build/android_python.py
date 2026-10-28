"""Resolve Android CPython distributions and configure cross-compilation."""

import shutil
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class PythonVersion(StrEnum):
    PY310 = "3.10"
    PY311 = "3.11"
    PY312 = "3.12"
    PY313 = "3.13"
    PY314 = "3.14"
    PY315 = "3.15"


class AndroidABI(StrEnum):
    ARM64 = "arm64-v8a"
    X86_64 = "x86_64"

    @property
    def triplet(self) -> str:
        return {
            AndroidABI.ARM64: "aarch64-linux-android",
            AndroidABI.X86_64: "x86_64-linux-android",
        }[self]


@dataclass(frozen=True)
class ChaquopyArchive:
    release: str

    def url(self, abi: AndroidABI) -> str:
        return (
            "https://chaquo.com/maven-central/com/chaquo/python/target/"
            f"{self.release}/target-{self.release}-{abi.value}.zip"
        )


@dataclass(frozen=True)
class CPythonArchive:
    base_url: str
    release: str

    def url(self, abi: AndroidABI) -> str:
        return f"{self.base_url}/python-{self.release}-{abi.triplet}.tar.gz"


PythonArchive = ChaquopyArchive | CPythonArchive

# 版本明确固定；更新运行库时同时更新此清单，不在下载失败时切换来源或版本。
PYTHON_ARCHIVES: dict[PythonVersion, PythonArchive] = {
    PythonVersion.PY310: ChaquopyArchive("3.10.22-0"),
    PythonVersion.PY311: ChaquopyArchive("3.11.17-0"),
    PythonVersion.PY312: ChaquopyArchive("3.12.15-0"),
    PythonVersion.PY313: CPythonArchive(
        "https://repo.maven.apache.org/maven2/com/chaquo/python/python/3.13.15",
        "3.13.15",
    ),
    PythonVersion.PY314: CPythonArchive(
        "https://www.python.org/ftp/python/3.14.8", "3.14.8"
    ),
    PythonVersion.PY315: CPythonArchive(
        "https://www.python.org/ftp/python/3.15.0", "3.15.0"
    ),
}


@dataclass(frozen=True)
class SysconfigRuntime:
    lib_dir: Path


@dataclass(frozen=True)
class PyO3ConfigRuntime:
    lib_dir: Path
    config_file: Path


PythonRuntime = SysconfigRuntime | PyO3ConfigRuntime


def download_archive(url: str, destination: Path) -> Path:
    """Download atomically; propagate failures without changing the source."""
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / url.rsplit("/", 1)[1]
    if not archive.is_file():
        partial = archive.with_name(archive.name + ".part")
        print(f"Downloading {url}", flush=True)
        try:
            urllib.request.urlretrieve(url, partial)
            partial.replace(archive)
        finally:
            partial.unlink(missing_ok=True)
    return archive


def write_pyo3_config(lib_dir: Path, version: PythonVersion) -> Path:
    """Describe Chaquopy's 64-bit, shared, GIL-enabled CPython ABI."""
    config_file = lib_dir.parent / "pyo3-config.txt"
    config_file.write_text(
        "implementation=CPython\n"
        f"version={version.value}\n"
        "shared=true\n"
        "abi3=false\n"
        "build_flags=\n"
        "pointer_width=64\n"
        f"lib_name=python{version.value}\n"
        f"lib_dir={lib_dir}\n"
        f"ext_suffix=.cpython-{version.value.replace('.', '')}.so\n",
        encoding="utf-8",
    )
    return config_file


def setup_python_cross_build(
    download_path: Path, python_version: str, target_triplet: str
) -> PythonRuntime:
    """Prepare a version- and architecture-specific Android Python runtime."""
    version = PythonVersion(python_version)
    abi = next(abi for abi in AndroidABI if abi.triplet == target_triplet)
    source = PYTHON_ARCHIVES[version]
    # 完整归档名包含补丁版本、构建号和 ABI，避免不同目标共用 prefix/lib。
    archive = download_archive(
        source.url(abi), download_path / "android-python" / "archives"
    )
    runtime_dir = (
        download_path
        / "android-python"
        / archive.name.removesuffix(".tar.gz").removesuffix(".zip")
    )
    lib_dir = runtime_dir / "prefix" / "lib"
    include_dir = lib_dir.parent / "include" / f"python{version.value}"
    if (
        not (runtime_dir / ".complete").is_file()
        or not (include_dir / "Python.h").is_file()
    ):
        if runtime_dir.exists():
            shutil.rmtree(runtime_dir)
        runtime_dir.mkdir(parents=True)
        match source:
            case ChaquopyArchive():
                lib_dir.mkdir(parents=True)
                with zipfile.ZipFile(archive) as zf:
                    for header in zf.namelist():
                        if header.startswith(
                            f"include/python{version.value}/"
                        ) and not header.endswith("/"):
                            if ".." in Path(header).parts:
                                raise ValueError("运行库头文件路径越界")
                            destination = runtime_dir / "prefix" / header
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            destination.write_bytes(zf.read(header))
                    member = f"jniLibs/{abi.value}/libpython{version.value}.so"
                    with (
                        zf.open(member) as src,
                        (lib_dir / f"libpython{version.value}.so").open("wb") as dst,
                    ):
                        shutil.copyfileobj(src, dst)
            case CPythonArchive():
                with tarfile.open(archive) as tf:
                    tf.extractall(runtime_dir, filter="data")
                if not list(lib_dir.rglob("_sysconfigdata*.py")):
                    raise FileNotFoundError(
                        f"归档缺少目标 Python 的 sysconfig 数据：{archive}"
                    )
        if not (lib_dir / f"libpython{version.value}.so").is_file():
            raise FileNotFoundError(f"归档缺少 libpython{version.value}.so：{archive}")
        if not (include_dir / "Python.h").is_file():
            raise FileNotFoundError(f"归档缺少目标 Python.h：{archive}")
        (runtime_dir / ".complete").touch()

    match source:
        case ChaquopyArchive():
            (lib_dir / f"python{version.value}").mkdir(exist_ok=True)
            return PyO3ConfigRuntime(lib_dir, write_pyo3_config(lib_dir, version))
        case CPythonArchive():
            return SysconfigRuntime(lib_dir)
