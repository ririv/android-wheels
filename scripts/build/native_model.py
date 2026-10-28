"""Represent native library names and explicit build systems."""

from dataclasses import asdict, dataclass
from enum import StrEnum


class NativeLibrary(StrEnum):
    LIBFFI = "libffi"
    LIBSODIUM = "libsodium"
    OPENSSL = "openssl"
    CRC32C = "crc32c"
    CARES = "cares"


class BuildSystem(StrEnum):
    AUTOTOOLS = "autotools"
    OPENSSL = "openssl"
    CMAKE = "cmake"


@dataclass(frozen=True)
class Library:
    name: NativeLibrary
    version: str
    filename: str
    url: str
    sha256: str
    system: BuildSystem
    args: tuple[str, ...]
    licenses: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "args": list(self.args),
            "licenses": list(self.licenses),
        }
