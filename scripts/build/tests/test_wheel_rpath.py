"""Reject build-machine paths at the ELF publication boundary."""

import unittest

from scripts.build.tests.test_wheel_abi import elf_with_dependency
from scripts.build.wheel_rpath import internal_paths, verify_rpaths


class WheelRpathTests(unittest.TestCase):
    def test_internal_dependency_paths_preserve_external_discovery_until_repair(self):
        data = elf_with_dependency("libarrow.so.2600")
        paths = internal_paths(
            data,
            "pyarrow/module.so",
            ("pyarrow/libarrow.so.2600",),
            ("/tmp/target-sdk/lib",),
        )
        self.assertEqual(paths, ("$ORIGIN", "/tmp/target-sdk/lib"))
        self.assertEqual(
            internal_paths(
                data, "pyarrow/module.so", ("pyarrow/libarrow.so.2600",), paths
            ),
            paths,
        )

    def test_existing_relative_path_resolves_a_dependency_without_choosing_another_copy(
        self,
    ):
        data = elf_with_dependency("libexample.so")
        paths = ("$ORIGIN/../private",)
        self.assertEqual(
            internal_paths(
                data,
                "package/module.so",
                ("private/libexample.so", "other/libexample.so"),
                paths,
            ),
            paths,
        )
        self.assertEqual(
            internal_paths(data, "package/module.so", ("private/libexample.so",), ()),
            ("$ORIGIN/../private",),
        )

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
