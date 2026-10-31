"""Keep source-bound bundled-library licenses in wheels without changing code."""

import hashlib
import json
import os
import re
import tempfile
import tomllib
import zipfile
from functools import cache
from pathlib import Path, PurePosixPath

from wheel.wheelfile import WheelFile

from scripts.pipeline.model import SdistSource, Target
from scripts.pipeline.sdists import download, extract

REGISTRY = Path(__file__).with_name("bundled-licenses.toml")


def license_rule(target: Target) -> dict | None:
    rules = tomllib.loads(REGISTRY.read_text())
    if target.library not in rules:
        return None
    rule = rules[target.library]
    if (
        not isinstance(target.source, SdistSource)
        or target.source.sha256 != rule["sdist-sha256"]
    ):
        raise ValueError("捆绑库许可证配置与固定上游源码不一致")
    if set(rule) != {"sdist-sha256", "sources"}:
        raise ValueError("捆绑库许可证配置存在未知字段")
    for source in rule["sources"]:
        if (
            set(source) != {"name", "url", "sha256", "filename", "files"}
            or not re.fullmatch(r"[a-z0-9-]+", source["name"])
            or Path(source["filename"]).name != source["filename"]
        ):
            raise ValueError("无效的捆绑库来源")
        for row in source["files"]:
            path = PurePosixPath(row["path"])
            if (
                set(row) != {"path", "sha256"}
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in row["path"]
                or not re.fullmatch(r"[a-f0-9]{64}", row["sha256"])
            ):
                raise ValueError("无效的许可证文件配置")
    return rule


def license_paths(rule: dict, prefix: str) -> dict[str, str]:
    return {
        prefix + "licenses/bundled/" + source["name"] + "/" + row["path"]: row["sha256"]
        for source in rule["sources"]
        for row in source["files"]
    }


def verify_bundled_licenses(
    archive: zipfile.ZipFile, target: Target, prefix: str
) -> None:
    rule = license_rule(target)
    if rule is None:
        return
    if json.loads(archive.read(prefix + "bundled-libraries.json")) != rule:
        raise ValueError("捆绑库许可证来源记录不一致")
    for path, sha256 in license_paths(rule, prefix).items():
        if hashlib.sha256(archive.read(path)).hexdigest() != sha256:
            raise ValueError(f"捆绑库许可证内容不一致：{path}")


@cache
def license_payload(library: str, source_sha256: str) -> dict[str, bytes]:
    rule = tomllib.loads(REGISTRY.read_text())[library]
    if rule["sdist-sha256"] != source_sha256:
        raise ValueError("捆绑库许可证下载来源不一致")
    result = {"bundled-libraries.json": (json.dumps(rule, indent=2) + "\n").encode()}
    with tempfile.TemporaryDirectory(prefix="wheel-licenses-") as temporary:
        root = Path(temporary)
        for source in rule["sources"]:
            archive = download(
                source["url"], source["sha256"], root / source["filename"]
            )
            directory = extract(archive, root / source["name"])
            for row in source["files"]:
                data = (directory / row["path"]).read_bytes()
                if hashlib.sha256(data).hexdigest() != row["sha256"]:
                    raise ValueError("固定来源中的许可证哈希不一致")
                result["licenses/bundled/" + source["name"] + "/" + row["path"]] = data
    return result


def attach_bundled_licenses(wheel: Path, target: Target) -> None:
    rule = license_rule(target)
    if rule is None:
        return
    with WheelFile(str(wheel)) as archive:
        (prefix,) = (
            name.removesuffix("METADATA")
            for name in archive.namelist()
            if name.endswith(".dist-info/METADATA")
        )
        if prefix + "bundled-libraries.json" in archive.namelist():
            verify_bundled_licenses(archive, target, prefix)
            return
    payload = license_payload(target.library, target.source.sha256)
    with tempfile.TemporaryDirectory(prefix="wheel-licenses-output-") as temporary:
        destination = Path(temporary) / wheel.name
        with (
            WheelFile(str(wheel)) as source,
            WheelFile(str(destination), "w") as output,
        ):
            for member in source.infolist():
                if not member.is_dir() and not member.filename.endswith(
                    (
                        ".dist-info/RECORD",
                        ".dist-info/RECORD.jws",
                        ".dist-info/RECORD.p7s",
                    )
                ):
                    output.writestr(member, source.read(member))
            for name, data in payload.items():
                output.writestr(prefix + name, data)
        os.replace(destination, wheel)
