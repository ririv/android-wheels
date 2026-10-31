"""Represent native library names and explicit build systems."""

from dataclasses import asdict, dataclass
from enum import StrEnum

from scripts.build.android_python import AndroidABI


class NativeLibrary(StrEnum):
    LIBFFI = "libffi"
    LIBSODIUM = "libsodium"
    OPENSSL = "openssl"
    OPENSSL_SHARED = "openssl-shared"
    CRC32C = "crc32c"
    JPEG = "jpeg"
    ICONV = "iconv"
    XML2 = "xml2"
    XSLT = "xslt"
    OPENBLAS = "openblas"
    GEOS = "geos"
    ARROW = "arrow"
    LIBPQ = "libpq"


class BuildSystem(StrEnum):
    AUTOTOOLS = "autotools"
    OPENSSL = "openssl"
    CMAKE = "cmake"
    CMAKE_SUPERBUILD = "cmake-superbuild"
    POSTGRESQL_CLIENT = "postgresql-client"


@dataclass(frozen=True)
class ABIArguments:
    arm64: tuple[str, ...] = ()
    x86_64: tuple[str, ...] = ()

    def for_abi(self, abi: AndroidABI) -> tuple[str, ...]:
        return {AndroidABI.ARM64: self.arm64, AndroidABI.X86_64: self.x86_64}[abi]


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
    abi_args: ABIArguments = ABIArguments()
    source_directory: str = "."

    def to_dict(self) -> dict:
        data = asdict(self)
        del data["abi_args"]
        del data["source_directory"]
        result = {
            **data,
            "args": list(self.args),
            "licenses": list(self.licenses),
        }
        if self.abi_args != ABIArguments():
            result["abi-args"] = {
                abi.value: list(self.abi_args.for_abi(abi)) for abi in AndroidABI
            }
        if self.source_directory != ".":
            result["source-directory"] = self.source_directory
        return result
