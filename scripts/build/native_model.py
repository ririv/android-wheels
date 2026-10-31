"""Represent native library names and explicit build systems."""

from dataclasses import asdict, dataclass
from enum import StrEnum

from scripts.build.android_python import AndroidABI


class NativeLibrary(StrEnum):
    LIBFFI = "libffi"
    LIBSODIUM = "libsodium"
    OPENSSL = "openssl"
    CRC32C = "crc32c"
    JPEG = "jpeg"
    ICONV = "iconv"
    XML2 = "xml2"
    XSLT = "xslt"
    OPENBLAS = "openblas"


class BuildSystem(StrEnum):
    AUTOTOOLS = "autotools"
    OPENSSL = "openssl"
    CMAKE = "cmake"


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

    def to_dict(self) -> dict:
        data = asdict(self)
        del data["abi_args"]
        result = {
            **data,
            "args": list(self.args),
            "licenses": list(self.licenses),
        }
        if self.abi_args != ABIArguments():
            result["abi-args"] = {
                abi.value: list(self.abi_args.for_abi(abi)) for abi in AndroidABI
            }
        return result
