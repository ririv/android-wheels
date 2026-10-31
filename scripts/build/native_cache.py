"""Identify and verify reusable native SDKs independently of Python versions."""

import argparse
import hashlib
import json
import os
import platform
import stat
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from scripts.build.native_libraries import library_specs
from scripts.pipeline.artifacts import digest
from scripts.pipeline.model import Target, load_plan

MANIFEST = ".native-cache.json"


@dataclass(frozen=True)
class CachedFile:
    path: str
    sha256: str
    mode: int
    kind: Literal["file"] = field(init=False, default="file")


@dataclass(frozen=True)
class CachedLink:
    path: str
    target: str
    kind: Literal["symlink"] = field(init=False, default="symlink")


def inventory(prefix: Path) -> list[dict]:
    entries: list[CachedFile | CachedLink] = []
    for path in sorted(prefix.rglob("*")):
        relative = path.relative_to(prefix).as_posix()
        if relative == MANIFEST:
            continue
        if path.is_symlink():
            entries.append(CachedLink(relative, os.readlink(path)))
        elif path.is_file():
            entries.append(
                CachedFile(relative, digest(path), stat.S_IMODE(path.stat().st_mode))
            )
        elif not path.is_dir():
            raise ValueError(f"原生缓存包含不支持的文件：{relative}")
    return [asdict(entry) for entry in entries]


def cache_key(target: Target, prefix: Path, ndk: Path) -> str:
    root = Path(__file__).resolve().parents[2]
    specs = library_specs(root / "scripts/build/native-libraries.toml")
    files = (
        "scripts/build/native_libraries.py",
        "scripts/build/native_model.py",
        "scripts/build/native_cache.py",
        "scripts/build/pg_config.py",
        "scripts/build/link_flags.py",
        "scripts/pipeline/sdists.py",
    )
    identity = {
        "libraries": [specs[name].to_dict() for name in target.native_dependencies],
        "abi": target.abi,
        "api": target.api,
        "environment": [asdict(value) for value in target.environment],
        "prefix": str(prefix.resolve()),
        "ndk": (ndk / "source.properties").read_text(),
        "host": [platform.system(), platform.machine()],
        "tools": {
            tool: subprocess.check_output([tool, "--version"], text=True).splitlines()[
                0
            ]
            for tool in ("cmake", "make")
        },
        "implementation": {name: digest(root / name) for name in files},
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return "android-native-" + hashlib.sha256(encoded).hexdigest()


def seal(prefix: Path, key: str) -> None:
    if not (prefix / "native-libraries.json").is_file():
        raise FileNotFoundError("原生 SDK 未完成构建，不能写入缓存")
    (prefix / MANIFEST).write_text(
        json.dumps({"key": key, "files": inventory(prefix)}, indent=2) + "\n"
    )


def verify(prefix: Path, key: str) -> None:
    manifest = json.loads((prefix / MANIFEST).read_text())
    if manifest != {"key": key, "files": inventory(prefix)}:
        raise ValueError("原生 SDK 缓存身份或文件校验失败")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    key = cache_key(
        load_plan(Path("build-plan.json")).target(os.environ["ARTIFACT"]),
        Path(os.environ["NATIVE_PREFIX"]),
        Path(os.environ["ANDROID_NDK"]),
    )
    with args.output.open("a") as output:
        output.write(f"key={key}\n")


if __name__ == "__main__":
    main()
