"""Check backend settings reach dependency discovery and compilation equally."""

import unittest
from unittest.mock import Mock

from scripts.build.pep517_settings import ConfiguredBuilder, backend_settings
from scripts.recipes.model import ConfigSetting


class ConfiguredBuilderTests(unittest.TestCase):
    def test_both_hooks_receive_the_same_explicit_settings(self):
        original = Mock(build_system_requires={"setuptools"})
        settings = backend_settings(
            (
                ConfigSetting("cmake.define.VALUE", "a b"),
                ConfigSetting("setup-args", "-Dblas=openblas"),
                ConfigSetting("setup-args", "-Dlapack=openblas"),
                ConfigSetting("setup-args", "-Duse-ilp64=false"),
            )
        )
        self.assertEqual(
            settings,
            {
                "cmake.define.VALUE": "a b",
                "setup-args": [
                    "-Dblas=openblas",
                    "-Dlapack=openblas",
                    "-Duse-ilp64=false",
                ],
            },
        )
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
