"""Compose the cibuildwheel PyO3 environment with existing Cargo configuration."""

import sys
import tomllib
from pathlib import Path

import tomli_w

from scripts.build.link_flags import PAGE_LINK_FLAGS, rust_link_flags


def configure(project: Path, virtual_env: Path, target_triplet: str) -> None:
    path = project / ".cargo" / "config.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    data.setdefault("env", {})["PYO3_CROSS_LIB_DIR"] = str(
        virtual_env.parent / "python" / "prefix" / "lib"
    )
    target = data.setdefault("target", {}).setdefault(target_triplet, {})
    target["rustflags"] = rust_link_flags(target.get("rustflags", []), PAGE_LINK_FLAGS)
    path.parent.mkdir(exist_ok=True)
    path.write_text(tomli_w.dumps(data), encoding="utf-8")


if __name__ == "__main__":
    configure(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
