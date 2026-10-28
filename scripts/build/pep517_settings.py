"""Compose PEP 517 hooks with one explicit set of backend settings."""

from dataclasses import dataclass
from typing import Protocol


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
    settings: dict[str, str]

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
