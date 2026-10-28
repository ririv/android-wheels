"""Verify the shared dependency groups and pinned tool configuration."""

import unittest

from scripts.tooling import configuration, requirements


class ToolingTests(unittest.TestCase):
    def test_build_and_dev_groups_share_one_dependency_definition(self):
        groups = configuration()["dependency-groups"]
        build = requirements("build", groups)
        dev = requirements("dev", groups)
        shared = requirements("shared", groups)
        self.assertTrue(set(shared).issubset(build))
        self.assertTrue(set(shared).issubset(dev))
        self.assertEqual(len(build), len(set(build)))
        self.assertEqual(len(requirements("toml", groups)), 1)
        self.assertTrue(all("==" in package for package in (*build, *dev)))

    def test_nested_groups_compose_and_deduplicate_dependencies(self):
        groups = {"one": ["a==1"], "two": [{"include-group": "one"}, "b==2", "a==1"]}
        self.assertEqual(requirements("two", groups), ("a==1", "b==2"))
