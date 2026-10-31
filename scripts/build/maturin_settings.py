"""Translate explicit Cargo feature selections into safe maturin arguments."""

import re
from dataclasses import dataclass
from enum import Enum

from scripts.recipes.model import ConfigSetting


class DefaultFeatures(Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"


@dataclass(frozen=True)
class MaturinOptions:
    features: tuple[str, ...] = ()
    defaults: DefaultFeatures = DefaultFeatures.ENABLED

    def arguments(self) -> tuple[str, ...]:
        return (
            *(
                ("--no-default-features",)
                if self.defaults == DefaultFeatures.DISABLED
                else ()
            ),
            *(("--features", ",".join(self.features)) if self.features else ()),
        )


def maturin_options(settings: tuple[ConfigSetting, ...]) -> MaturinOptions:
    features = []
    defaults = DefaultFeatures.ENABLED
    selections = []
    for setting in settings:
        match setting.name:
            case "features":
                if not re.fullmatch(
                    r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)?", setting.value
                ):
                    raise ValueError("maturin features 必须逐项给出 Cargo feature 名称")
                features.append(setting.value)
            case "no-default-features":
                selections.append(setting.value)
            case name:
                raise ValueError(f"尚未接入的 maturin 参数：{name}")
    if selections:
        match selections:
            case ["true"]:
                defaults = DefaultFeatures.DISABLED
            case ["false"]:
                defaults = DefaultFeatures.ENABLED
            case _:
                raise ValueError(
                    "no-default-features 必须恰好为一个 true 或 false 字符串"
                )
    return MaturinOptions(tuple(dict.fromkeys(features)), defaults)
