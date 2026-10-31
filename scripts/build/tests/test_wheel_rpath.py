"""Reject build-machine paths at the ELF publication boundary."""

import unittest

from scripts.build.tests.test_wheel_abi import elf_with_dependency
from scripts.build.wheel_rpath import verify_rpaths


class WheelRpathTests(unittest.TestCase):
    def test_android_libraries_use_only_origin_relative_search_paths(self):
        for path in (None, "$ORIGIN", "$ORIGIN/../numpy.libs:${ORIGIN}/lib"):
            with self.subTest(path=path):
                verify_rpaths(
                    elf_with_dependency("libpython3.13.so", path), "module.so"
                )
        for path in (
            "/tmp/build/python/lib",
            "$ORIGIN:/home/runner/lib",
            "",
            "../lib",
            "$ORIGINevil/lib",
        ):
            with (
                self.subTest(path=path),
                self.assertRaisesRegex(ValueError, "不可移植"),
            ):
                verify_rpaths(
                    elf_with_dependency("libpython3.13.so", path), "module.so"
                )
