"""Run one explicit stage of the build pipeline."""

import argparse
import json
import os
from pathlib import Path

from scripts.pipeline.artifacts import collect, record
from scripts.pipeline.model import load_plan
from scripts.pipeline.notifications import notify_index, notify_legacy
from scripts.pipeline.planning import manual_plan, recipe_plan, write_actions_plan
from scripts.pipeline.publish import publish
from scripts.pipeline.source import verify_checkout
from scripts.recipes.model import Publication


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("notify-index", "notify-legacy"):
        command = commands.add_parser(name)
        command.add_argument("--repository", required=True)
    local = commands.add_parser("plan-local")
    local.add_argument("--recipes", required=True)
    local.add_argument("--python-versions", default="recipe")
    local.add_argument("--version-tag", default="")
    local.add_argument("--publication", type=Publication, default=Publication.BUILD)
    local.add_argument("--output", type=Path, default=Path("build-plan.json"))
    local.add_argument("--github-output", type=Path, required=True)
    for name in ("plan", "plan-source"):
        command = commands.add_parser(name)
        command.add_argument("--event", type=Path, required=True)
        command.add_argument("--event-name", required=True)
        command.add_argument("--github-output", type=Path, required=True)
        command.add_argument("--output", type=Path, default=Path("build-plan.json"))
    for name in ("verify-source", "record", "publish"):
        command = commands.add_parser(name)
        command.add_argument("--plan", type=Path, default=Path("build-plan.json"))
        if name == "publish":
            command.add_argument("--artifacts", type=Path, required=True)
        else:
            command.add_argument("--artifact", required=True)
            command.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    if args.command in {"notify-index", "notify-legacy"}:
        print(
            notify_index(args.repository)
            if args.command == "notify-index"
            else notify_legacy(args.repository)
        )
        return
    if args.command in {"plan", "plan-source", "plan-local"}:
        event = (
            {
                "inputs": {
                    "recipes": args.recipes,
                    "python_versions": args.python_versions,
                    "version_tag": args.version_tag,
                    "publication": args.publication.value,
                }
            }
            if args.command == "plan-local"
            else json.loads(args.event.read_text(encoding="utf-8"))
        )
        plan = (
            manual_plan(event)
            if args.command == "plan-source"
            else recipe_plan(
                "workflow_dispatch"
                if args.command == "plan-local"
                else args.event_name,
                event,
                Path.cwd(),
            )
        )
        write_actions_plan(plan, args.output, args.github_output)
        print(args.output.read_text(encoding="utf-8"))
        return
    plan = load_plan(args.plan)
    if args.command == "verify-source":
        verify_checkout(plan.target(args.artifact).source, args.directory)
    elif args.command == "record":
        record(args.directory, plan.target(args.artifact))
    else:
        if plan.publication != Publication.PUBLISH:
            raise ValueError("当前计划只允许生成 Actions 产物，禁止发布")
        wheels = collect(args.artifacts, plan)
        result = publish(
            Path.cwd(),
            wheels,
            f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
        )
        print(result)


if __name__ == "__main__":
    main()
