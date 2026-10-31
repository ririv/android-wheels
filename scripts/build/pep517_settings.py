"""Compose PEP 517 hooks with one explicit set of backend settings."""

from dataclasses import dataclass
from typing import Protocol

from scripts.recipes.model import ConfigSetting


def backend_settings(settings: tuple[ConfigSetting, ...]) -> dict[str, str | list[str]]:
    """Preserve repeated PEP 517 keys as ordered arrays."""
    result: dict[str, str | list[str]] = {}
    for setting in settings:
        if setting.name not in result:
            result[setting.name] = setting.value
        else:
            existing = result[setting.name]
            result[setting.name] = (
                [existing, setting.value]
                if isinstance(existing, str)
                else [*existing, setting.value]
            )
    return result


class ProjectBuilder(Protocol):
    @property
    def build_system_requires(self) -> set[str]: ...

    def get_requires_for_build(
        self, distribution, config_settings=None
    ) -> set[str]: ...

    def build(self, distribution, output_directory, config_settings=None) -> str: ...


@dataclass(frozen=True)
class ConfiguredBuilder:
    builder: ProjectBuilder
    settings: dict[str, str | list[str]]

    @property
    def build_system_requires(self) -> set[str]:
        return self.builder.build_system_requires

    def get_requires_for_build(self, distribution) -> set[str]:
        return self.builder.get_requires_for_build(
            distribution, config_settings=self.settings
        )

    def build(self, distribution, output_directory) -> str:
        return self.builder.build(
            distribution, output_directory, config_settings=self.settings
        )
