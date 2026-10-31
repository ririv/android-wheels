"""Assemble a pinned scientific stack and run it on a selected Android device."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from scripts.pipeline.artifacts import artifact_wheel, digest
from scripts.pipeline.model import load_plan
from scripts.pipeline.sdists import download
from scripts.testing.runtime_files import manifest_resources
from scripts.testing.runtime_suites import SUITES, ArtifactLayout, RuntimeSuite, Suite

REPOSITORY = "ririv/py-extra-wheels"
ROOT = Path(__file__).resolve().parents[2]


def published_dependencies(
    abi: str,
    output: Path,
    packages: tuple[str, ...] = SUITES[RuntimeSuite.PLOTTING].published,
) -> list[str]:
    matrix = json.loads((ROOT / "docs/data/python-matrix-2026-10.json").read_text())
    numpy = json.loads((ROOT / "docs/data/numpy-2026-10.json").read_text())
    scientific = json.loads((ROOT / "docs/data/scientific-2026-10.json").read_text())
    processing = json.loads(
        (ROOT / "docs/data/data-processing-2026-10.json").read_text()
    )
    entries = (
        [
            (matrix["publication"]["wheels_commit"], row)
            for row in matrix["publication"]["published_wheels"]
        ]
        + [(numpy["publication"]["revision"], row) for row in numpy["wheels"]]
        + [(scientific["publication"]["revision"], row) for row in scientific["wheels"]]
        + [(processing["publication"]["revision"], row) for row in processing["wheels"]]
    )
    entries = [
        (commit, row)
        for commit, row in entries
        if row["target"]["python"] == "3.13"
        and row["target"]["abi"] == abi
        and row["target"]["library"] in packages
    ]
    if len(entries) != len(packages) or {
        row["target"]["library"] for _, row in entries
    } != set(packages):
        raise ValueError("已发布的运行依赖与测试套件声明不一致")
    plan_file = output / "published-plan.json"
    plan_file.write_text(
        json.dumps(
            {
                "publication": "build",
                "targets": [row["target"] for _, row in entries],
                "skipped": [],
            }
        )
    )
    plan = load_plan(plan_file)
    arguments = []
    for commit, row in entries:
        target = next(t for t in plan.targets if t.library == row["target"]["library"])
        folder = output / target.artifact
        folder.mkdir(exist_ok=True)
        wheel = download(
            f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{target.library}/{row['filename']}",
            row["sha256"],
            folder / row["filename"],
        )
        (folder / "manifest.json").write_text(
            json.dumps(
                {
                    "target": target.to_dict(),
                    "wheel": wheel.name,
                    "sha256": row["sha256"],
                }
            )
        )
        arguments.extend(["--dependency", str(plan_file), str(folder)])
    return arguments


def build_dependencies(
    runs: str, abi: str, output: Path, layout: ArtifactLayout, suite: Suite
) -> tuple[Path, Path, list[str]]:
    selected = {}
    for run in runs.split(","):
        folder = output / ("run-" + run)
        subprocess.run(
            [
                "gh",
                "run",
                "download",
                run,
                "--repo",
                REPOSITORY,
                "--name",
                "build-plan",
                "--dir",
                str(folder / "plan"),
            ],
            check=True,
        )
        plan_file = folder / "plan/build-plan.json"
        plan = load_plan(plan_file)
        available = set(
            subprocess.check_output(
                [
                    "gh",
                    "api",
                    "--paginate",
                    f"repos/{REPOSITORY}/actions/runs/{run}/artifacts?per_page=100",
                    "--jq",
                    ".artifacts[].name",
                ],
                text=True,
            ).splitlines()
        )
        if layout == ArtifactLayout.REPACKAGED:
            subprocess.run(
                [
                    "gh",
                    "run",
                    "download",
                    run,
                    "--repo",
                    REPOSITORY,
                    "--name",
                    "repackaged-wheels",
                    "--dir",
                    str(folder / "artifacts"),
                ],
                check=True,
            )
        for target in plan.targets:
            if (
                target.library not in suite.packages
                or target.python.value != "3.13"
                or target.abi.value != abi
                or (layout == ArtifactLayout.BUILD and target.artifact not in available)
            ):
                continue
            artifact = (
                folder if layout == ArtifactLayout.BUILD else folder / "artifacts"
            ) / target.artifact
            if layout == ArtifactLayout.BUILD:
                subprocess.run(
                    [
                        "gh",
                        "run",
                        "download",
                        run,
                        "--repo",
                        REPOSITORY,
                        "--name",
                        target.artifact,
                        "--dir",
                        str(artifact),
                    ],
                    check=True,
                )
            wheel = artifact_wheel(artifact, target)
            if target.library in selected:
                previous_plan, previous_artifact, previous_hash = selected[
                    target.library
                ]
                if (
                    previous_hash != digest(wheel)
                    or load_plan(previous_plan).target(previous_artifact.name) != target
                ):
                    raise ValueError(f"同一包存在不同运行产物：{target.library}")
            selected[target.library] = (plan_file, artifact, digest(wheel))
    if set(selected) != set(suite.packages):
        raise ValueError(
            f"缺少科学计算产物：{sorted(set(suite.packages) - set(selected))}"
        )
    plan_file, artifact, _ = selected.pop(suite.entry)
    arguments = []
    for dependency_plan, dependency_artifact, _ in selected.values():
        arguments.extend(
            ["--dependency", str(dependency_plan), str(dependency_artifact)]
        )
    return plan_file, artifact, arguments


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", required=True)
    parser.add_argument(
        "--layout",
        type=ArtifactLayout,
        choices=list(ArtifactLayout),
        default=ArtifactLayout.BUILD,
    )
    parser.add_argument(
        "--suite",
        type=RuntimeSuite,
        choices=list(RuntimeSuite),
        default=RuntimeSuite.PLOTTING,
    )
    parser.add_argument("--abi", choices=["arm64-v8a", "x86_64"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--resource", nargs=2, action="append", default=[])
    parser.add_argument("--resource-manifest", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+(?:,[0-9]+)*", args.runs):
        raise ValueError("运行编号必须是逗号分隔的数字")
    suite = SUITES[args.suite]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    plan, artifact, arguments = build_dependencies(
        args.runs, args.abi, output, args.layout, suite
    )
    arguments.extend(published_dependencies(args.abi, output, suite.published))
    pure = json.loads(Path(__file__).with_name(suite.pure_lock).read_text())
    for row in pure:
        wheel = download(row["url"], row["sha256"], output / row["filename"])
        arguments.extend(["--pure-dependency", str(wheel), row["sha256"]])
    for path, sha256 in args.resource:
        arguments.extend(["--resource", path, sha256])
    if args.resource_manifest is not None:
        for path, sha256 in manifest_resources(args.resource_manifest):
            arguments.extend(["--resource", path, sha256])
    subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "scripts.testing.android_runtime",
            "--plan",
            str(plan),
            "--artifact",
            str(artifact),
            "--adb",
            str(args.adb),
            "--serial",
            args.serial,
            "--toolchain",
            str(args.toolchain),
            "--script",
            str(Path(__file__).with_name(suite.script)),
            "--report",
            str(args.report),
            *arguments,
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
