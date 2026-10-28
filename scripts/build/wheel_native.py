"""Keep pinned native dependency provenance and licenses inside repaired wheels."""

import json
import os
import tempfile
from pathlib import Path

from wheel.wheelfile import WheelFile

from scripts.build.native_model import NativeLibrary


def attach_native_metadata(wheel: Path) -> None:
    names = tuple(
        NativeLibrary(name)
        for name in os.environ["NATIVE_DEPENDENCIES"].split(",")
        if name
    )
    if not names:
        return
    prefix = Path(os.environ["NATIVE_PREFIX"])
    metadata = (prefix / "native-libraries.json").read_bytes()
    if tuple(row["name"] for row in json.loads(metadata)) != names:
        raise ValueError("已编译的原生依赖与构建目标不一致")
    with tempfile.TemporaryDirectory(prefix="wheel-native-") as temporary:
        destination = Path(temporary) / wheel.name
        with (
            WheelFile(str(wheel)) as source,
            WheelFile(str(destination), "w") as output,
        ):
            info = [
                name.removesuffix("METADATA")
                for name in source.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            if len(info) != 1:
                raise ValueError("wheel 必须包含唯一发行元数据")
            for member in source.infolist():
                if not member.filename.endswith(
                    (
                        ".dist-info/RECORD",
                        ".dist-info/RECORD.jws",
                        ".dist-info/RECORD.p7s",
                    )
                ):
                    output.writestr(member, source.read(member))
            output.writestr(info[0] + "native-libraries.json", metadata)
            for license_file in sorted((prefix / "licenses").rglob("*")):
                if license_file.is_file():
                    relative = license_file.relative_to(prefix / "licenses").as_posix()
                    output.writestr(
                        info[0] + "licenses/native/" + relative,
                        license_file.read_bytes(),
                    )
        os.replace(destination, wheel)
