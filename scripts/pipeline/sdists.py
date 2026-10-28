"""Download pinned official sdists and extract their unchanged release sources."""

import hashlib
import shutil
import tarfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath


def download(url: str, expected: str, destination: Path) -> Path:
    request = urllib.request.Request(url, headers={"User-Agent": "py-extra-wheels/1"})
    with (
        urllib.request.urlopen(request, timeout=60) as response,
        destination.open("wb") as output,
    ):
        shutil.copyfileobj(response, output)
    with destination.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        destination.unlink()
        raise ValueError("PyPI sdist SHA-256 不匹配")
    return destination


def extract(archive: Path, destination: Path) -> Path:
    if destination.exists():
        raise FileExistsError(f"源码解包目录必须不存在：{destination}")
    destination.mkdir(parents=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                path = PurePosixPath(member.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in member.filename:
                    raise ValueError("sdist ZIP 包含非法路径")
            source.extractall(destination)
    elif archive.name.endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".tgz")):
        with tarfile.open(archive) as source:
            source.extractall(destination, filter="data")
    else:
        raise ValueError(f"不支持的 sdist 格式：{archive.name}")
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError("sdist 必须包含唯一源码根目录")
    return roots[0]
