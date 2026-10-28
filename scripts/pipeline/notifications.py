"""Request downstream synchronization until its published acknowledgement matches."""

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from scripts.pipeline.source import github
from scripts.tooling import settings


@dataclass(frozen=True)
class NeverPublished:
    pass


@dataclass(frozen=True)
class PublishedState:
    tree: str


PublicationState = NeverPublished | PublishedState


@dataclass(frozen=True)
class AlreadySynchronized:
    tree: str


@dataclass(frozen=True)
class SynchronizationRequested:
    tree: str


SynchronizationResult = AlreadySynchronized | SynchronizationRequested


def published_state(url: str) -> PublicationState:
    request = urllib.request.Request(
        f"{url}?check={uuid4().hex}", headers={"Cache-Control": "no-cache"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        error.close()
        if error.code == 404:
            # 404 表示接收端还没有发布状态标记；其他网络和权限错误必须报告。
            return NeverPublished()
        raise
    if set(data) != {"tree"} or not re.fullmatch(r"[a-f0-9]{40}", data["tree"]):
        raise ValueError(f"无效的下游发布状态：{url}")
    return PublishedState(data["tree"])


def ensure_synchronized(
    tree: str, state: PublicationState, request: Callable[[], None]
) -> SynchronizationResult:
    match state:
        case PublishedState(tree=published) if published == tree:
            return AlreadySynchronized(tree)
        case NeverPublished() | PublishedState():
            request()
            return SynchronizationRequested(tree)


def notify_index(repository: str) -> SynchronizationResult:
    tree = github(f"repos/{repository}/commits/wheels")["commit"]["tree"]["sha"]
    state = published_state(f"{settings()['index-url']}/index-state.json")
    return ensure_synchronized(
        tree,
        state,
        lambda: subprocess.run(
            [
                "gh",
                "workflow",
                "run",
                "pages.yml",
                "--repo",
                repository,
                "--ref",
                "main",
            ],
            check=True,
        ),
    )


def notify_legacy(repository: str) -> SynchronizationResult:
    config = settings()
    tree = github(f"repos/{repository}/commits/gh-pages")["commit"]["tree"]["sha"]
    state = published_state(f"{config['legacy-index-url']}/sync-state.json")

    def request() -> None:
        subprocess.run(
            [
                "gh",
                "workflow",
                "run",
                "sync-wheel-index.yml",
                "--repo",
                config["legacy-repository"],
                "--ref",
                "main",
            ],
            check=True,
            env={**os.environ, "GH_TOKEN": os.environ["LEGACY_INDEX_DISPATCH_TOKEN"]},
        )

    return ensure_synchronized(tree, state, request)
