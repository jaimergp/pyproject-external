# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

"""
Constants used throughout the codebase. All variables need to be typed as `Final`.
"""

from enum import StrEnum
from typing import Final

APP_NAME: Final[str] = "pyproject-external"
APP_AUTHOR: Final[str] = "pyproject-external"
APP_CONFIG_FILENAME: Final[str] = "config.toml"
DEFAULT_ECOSYSTEMS_SCHEMA_URL: Final[str] = (
    "https://raw.githubusercontent.com/jaimergp/external-metadata-mappings/ubuntu-26/"
    "schemas/known-ecosystems.schema.json"
)
DEFAULT_ECOSYSTEMS_URL: Final[str] = (
    "https://raw.githubusercontent.com/jaimergp/external-metadata-mappings/ubuntu-26/"
    "data/known-ecosystems.json"
)
DEFAULT_MAPPING_SCHEMA_URL: Final[str] = (
    "https://raw.githubusercontent.com/jaimergp/external-metadata-mappings/ubuntu-26/"
    "schemas/external-mapping.schema.json"
)
DEFAULT_REGISTRY_SCHEMA_URL: Final[str] = (
    "https://raw.githubusercontent.com/jaimergp/external-metadata-mappings/ubuntu-26/"
    "schemas/central-registry.schema.json"
)
DEFAULT_REGISTRY_URL: Final[str] = (
    "https://raw.githubusercontent.com/jaimergp/external-metadata-mappings/ubuntu-26/data/registry.json"
)


class PythonInstallers(StrEnum):
    PIP = "pip"
    UV = "uv"


class UnsupportedConstraintsBehaviour(StrEnum):
    ERROR = "error"
    WARN = "warn"
    IGNORE = "ignore"
