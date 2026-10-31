"""Deploy hash-verified data fixtures without replacing runtime files."""

import json
import re
import shutil
from pathlib import Path

from scripts.pipeline.artifacts import digest


def manifest_resources(path: Path) -> list[list[str]]:
    """Expand an explicit fixture manifest relative to its own directory."""
    rows = json.loads(path.read_text())
    if not isinstance(rows, list):
        raise ValueError("运行资源清单必须是数组")
    result = []
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"filename", "sha256"}
            or not isinstance(row["filename"], str)
            or Path(row["filename"]).name != row["filename"]
            or not isinstance(row["sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", row["sha256"])
        ):
            raise ValueError("运行资源清单包含无效文件声明")
        result.append([str(path.parent / row["filename"]), row["sha256"]])
    return result


def copy_resources(resources: list[list[str]], destination: Path) -> list[dict]:
    report = []
    for filename, expected in resources:
        source = Path(filename)
        target = destination / source.name
        if not source.is_file() or digest(source) != expected:
            raise ValueError(f"运行资源哈希校验失败：{source.name}")
        if target.exists():
            raise FileExistsError(f"运行资源不能覆盖现有文件：{source.name}")
        shutil.copy2(source, target)
        report.append({"filename": source.name, "sha256": expected})
    return report
