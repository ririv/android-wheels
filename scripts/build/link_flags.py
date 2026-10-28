"""Compose Android linker arguments without discarding project Rust flags."""

import shlex

PAGE_SIZE = 16384
PAGE_LINK_FLAGS = (
    f"-Wl,-z,max-page-size={PAGE_SIZE}",
    f"-Wl,-z,common-page-size={PAGE_SIZE}",
)


def rust_link_flags(existing: list[str] | str, arguments: tuple[str, ...]) -> list[str]:
    result = shlex.split(existing) if isinstance(existing, str) else list(existing)
    for argument in arguments:
        pair = ["-C", f"link-arg={argument}"]
        if not any(result[i : i + 2] == pair for i in range(len(result))):
            result.extend(pair)
    return result
