"""Verify alignment boundaries using real ELF program headers."""

import io
import struct
import unittest

from scripts.build.wheel_alignment import verify_alignment


def elf_with_load_segment(alignment: int, address: int = 0) -> bytes:
    header = struct.pack(
        "<16sHHIQQQIHHHHHH",
        b"\x7fELF\x02\x01\x01" + b"\0" * 9,
        3,
        183,
        1,
        0,
        64,
        0,
        0,
        64,
        56,
        1,
        64,
        0,
        0,
    )
    return header + struct.pack(
        "<IIQQQQQQ", 1, 5, 0, address, address, 120, 120, alignment
    )


class WheelAlignmentTests(unittest.TestCase):
    def test_load_segments_accept_16k_and_larger_alignment(self):
        for alignment in (16384, 65536):
            with self.subTest(alignment=alignment):
                verify_alignment(
                    io.BytesIO(elf_with_load_segment(alignment)), "extension.so"
                )

    def test_4k_segments_and_incongruent_addresses_are_rejected(self):
        for alignment, address in ((4096, 0), (16384, 4096)):
            with self.subTest(alignment=alignment, address=address):
                with self.assertRaisesRegex(ValueError, "16384"):
                    verify_alignment(
                        io.BytesIO(elf_with_load_segment(alignment, address)),
                        "dependency.so",
                    )
