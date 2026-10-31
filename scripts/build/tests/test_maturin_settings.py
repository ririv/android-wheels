"""Verify explicit Cargo feature options preserve the default build interface."""

import unittest

from scripts.build.maturin_settings import (
    DefaultFeatures,
    MaturinOptions,
    maturin_options,
)
from scripts.recipes.model import ConfigSetting


class MaturinSettingsTests(unittest.TestCase):
    def test_default_and_explicit_feature_selections(self):
        self.assertEqual(maturin_options(()), MaturinOptions())
        self.assertEqual(maturin_options(()).arguments(), ())
        options = maturin_options(
            (
                ConfigSetting("features", "csv"),
                ConfigSetting("features", "polars-python/json"),
                ConfigSetting("no-default-features", "true"),
            )
        )
        self.assertEqual(options.defaults, DefaultFeatures.DISABLED)
        self.assertEqual(
            options.arguments(),
            ("--no-default-features", "--features", "csv,polars-python/json"),
        )
        self.assertEqual(
            maturin_options((ConfigSetting("features", "csv"),)).arguments(),
            ("--features", "csv"),
        )

    def test_backend_boundary_rejects_unsupported_or_malformed_arguments(self):
        for settings in [
            (ConfigSetting("build-args", "--arbitrary"),),
            (ConfigSetting("features", "--no-default-features"),),
            (ConfigSetting("no-default-features", "true false"),),
        ]:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                maturin_options(settings)
