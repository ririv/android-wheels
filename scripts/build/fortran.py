"""Compose cibuildwheel's lazy Fortran shim with the real Android compiler."""

import shlex
from collections.abc import Callable
from pathlib import Path


def configure_fortran(
    environment: dict[str, str],
    compiler: Path,
    install_shim: Callable[[dict[str, str]], None],
) -> None:
    install_shim(environment)
    shim = Path(environment["FC"])
    launcher = shim.with_name("android-flang")
    launcher.write_text(
        "#!/bin/sh\nCC="
        + shlex.quote(str(compiler))
        + " exec "
        + shlex.quote(str(shim))
        + ' "$@"\n'
    )
    launcher.chmod(0o755)
    environment["FC"] = str(launcher)
