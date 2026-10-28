"""Resolve declared package environment without changing toolchain ownership."""

import shlex
import unittest

from scripts.build.android_python import AndroidABI, PythonVersion
from scripts.pipeline.model import GitSource, Target
from scripts.pipeline.planning import resolve_environment
from scripts.recipes.load import environment
from scripts.recipes.model import Backend


class EnvironmentTests(unittest.TestCase):
    def test_target_reference_is_resolved_independently_for_each_abi(self):
        settings = environment({"LIBUV_CONFIGURE_HOST": {"target": "triplet"}})
        for abi in AndroidABI:
            variables = resolve_environment(settings, PythonVersion.PY313, abi, 24)
            self.assertEqual(variables[0].name, "LIBUV_CONFIGURE_HOST")
            self.assertEqual(variables[0].value, abi.triplet)

    def test_literal_values_keep_spaces_as_one_environment_assignment(self):
        settings = environment({"EXAMPLE_OPTIONS": "two words $(literal)"})
        source = GitSource("owner/repo", "main", "a" * 40, ".", Backend.SETUPTOOLS)
        target = Target(
            "example",
            source,
            PythonVersion.PY313,
            AndroidABI.ARM64,
            24,
            resolve_environment(settings, PythonVersion.PY313, AndroidABI.ARM64, 24),
        )
        self.assertEqual(
            shlex.split(target.row()["cibw_environment"]),
            ["EXAMPLE_OPTIONS=two words $(literal)"],
        )

    def test_toolchain_override_and_invalid_external_values_are_rejected(self):
        for value in (
            {"CC": "gcc"},
            {"CIBW_BUILD": "*"},
            {"HOST_PYTHON": "/host"},
            {"EXAMPLE": True},
            {"EXAMPLE": "bad\nvalue"},
            {"EXAMPLE": {"target": "unknown"}},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                environment(value)
