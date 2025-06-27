# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
import os
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from platformdirs import user_config_dir

from ._constants import APP_AUTHOR, APP_CONFIG_FILENAME, APP_NAME


def _get_config_directory() -> Path:
    if pyproject_external_config := os.environ.get("PYPROJECT_EXTERNAL_CONFIG"):
        return Path(pyproject_external_config)
    return Path(user_config_dir(appname=APP_NAME, appauthor=APP_AUTHOR))


def _get_config_file() -> Path:
    return _get_config_directory() / APP_CONFIG_FILENAME


@dataclass(frozen=True, kw_only=True)
class Config:
    preferred_package_manager: str | None = None

    @classmethod
    def load_user_config(cls) -> "Config":
        config_file = _get_config_file()
        if config_file.is_file():
            return cls(**tomllib.loads(_get_config_file().read_text()))
        return cls()
