"""Represent explicitly requested cross-compilation tools."""

from enum import StrEnum


class BuildTool(StrEnum):
    FORTRAN = "fortran"
