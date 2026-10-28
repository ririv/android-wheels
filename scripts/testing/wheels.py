"""Create complete wheel fixtures with internally consistent PEP 427 metadata."""

import base64
import csv
import hashlib
import io
import zipfile
from pathlib import Path


def write_wheel(path: Path, files: dict[str, bytes]) -> None:
    prefix = next(
        name.removesuffix("METADATA")
        for name in files
        if name.endswith(".dist-info/METADATA")
    )
    record = prefix + "RECORD"
    rows = []
    for name, data in files.items():
        encoded = (
            base64.urlsafe_b64encode(hashlib.sha256(data).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        rows.append((name, f"sha256={encoded}", str(len(data))))
    rows.append((record, "", ""))
    text = io.StringIO()
    csv.writer(text, lineterminator="\n").writerows(rows)
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        archive.writestr(record, text.getvalue())
