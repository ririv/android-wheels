"""Expose target libpq build metadata through a relocatable host-side tool."""

from pathlib import Path


def write_pg_config(prefix: Path, version: str) -> None:
    binary = prefix / "host-tools/bin/pg_config"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text(
        "#!/usr/bin/env python3\n"
        '"""Query the installed Android libpq prefix without executing target code."""\n'
        "import sys\n"
        "from pathlib import Path\n"
        "prefix = Path(__file__).resolve().parents[2]\n"
        "values = {\n"
        f'    "--version": "PostgreSQL {version}",\n'
        '    "--libdir": str(prefix / "lib"),\n'
        '    "--includedir": str(prefix / "include"),\n'
        '    "--includedir-server": str(prefix / "include/postgresql/server"),\n'
        '    "--cppflags": "-I" + str(prefix / "include"),\n'
        '    "--ldflags": "-L" + str(prefix / "lib"),\n'
        "}\n"
        "if len(sys.argv) != 2 or sys.argv[1] not in values:\n"
        '    sys.exit("pg_config: unsupported query")\n'
        "print(values[sys.argv[1]])\n"
    )
    binary.chmod(0o755)
