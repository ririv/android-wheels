"""Install one verified native SDK into a builder's target Python prefix."""

import json
import shutil
from pathlib import Path

from scripts.build.native_libraries import library_specs
from scripts.build.native_model import NativeLibrary


def install_libraries(
    source: Path, destination: Path, names: tuple[NativeLibrary, ...]
) -> None:
    specs = library_specs(Path(__file__).with_name("native-libraries.toml"))
    expected = [specs[name].to_dict() for name in names]
    if json.loads((source / "native-libraries.json").read_text()) != expected:
        raise ValueError("提前编译的原生依赖与当前目标不一致")
    shutil.copytree(source, destination, dirs_exist_ok=True)
