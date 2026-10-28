"""Reject ELF load segments that cannot satisfy Android 16 KB alignment."""

from typing import BinaryIO

from elftools.elf.elffile import ELFFile

from scripts.build.link_flags import PAGE_SIZE


def verify_alignment(stream: BinaryIO, name: str) -> None:
    for segment in ELFFile(stream).iter_segments():
        if segment["p_type"] != "PT_LOAD":
            continue
        if (
            segment["p_align"] < PAGE_SIZE
            or (segment["p_offset"] - segment["p_vaddr"]) % PAGE_SIZE
        ):
            raise ValueError(f"ELF 加载段未按 {PAGE_SIZE} 字节对齐：{name}")
