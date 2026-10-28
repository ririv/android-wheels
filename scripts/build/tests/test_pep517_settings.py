"""Check backend settings reach dependency discovery and compilation equally."""

import unittest
from unittest.mock import Mock

from scripts.build.pep517_settings import ConfiguredBuilder


class ConfiguredBuilderTests(unittest.TestCase):
    def test_both_hooks_receive_the_same_explicit_settings(self):
        original = Mock(build_system_requires={"setuptools"})
        settings = {"cmake.define.VALUE": "a b"}
        builder = ConfiguredBuilder(original, settings)
        self.assertEqual(builder.build_system_requires, {"setuptools"})
        builder.get_requires_for_build("wheel")
        builder.build("wheel", "dist")
        original.get_requires_for_build.assert_called_once_with(
            "wheel", config_settings=settings
        )
        original.build.assert_called_once_with(
            "wheel", "dist", config_settings=settings
        )
