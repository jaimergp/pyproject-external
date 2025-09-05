# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

"""
User configuration utilities.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import tomllib
except ImportError:
    import tomli as tomllib

if TYPE_CHECKING:
    try:
        from typing import Self
    except ImportError:  # py 3.11+ required for Self
        from typing_extensions import Self

from platformdirs import user_config_dir

from ._constants import APP_AUTHOR, APP_CONFIG_FILENAME, APP_NAME, UnsupportedConstraintsBehaviour


def _get_config_directory() -> Path:
    if pyproject_external_config := os.environ.get("PYPROJECT_EXTERNAL_CONFIG_DIR"):
        return Path(pyproject_external_config)
    return Path(user_config_dir(appname=APP_NAME, appauthor=APP_AUTHOR))


def _get_config_file() -> Path:
    return _get_config_directory() / APP_CONFIG_FILENAME


@dataclass(kw_only=True)
class Config:
    """
    User configuration for the `-m pyproject_external` CLI.
    """

    #: Which package manager to use by default on this system, instead of autodetected.
    preferred_package_manager: str = ""
    unsupported_constraints_behaviour: UnsupportedConstraintsBehaviour = (
        UnsupportedConstraintsBehaviour.WARN
    )

    def __post_init__(self):
        if not isinstance(self.preferred_package_manager, str):
            raise ValueError(
                "'preferred_package_manager' must be str, but found "
                f"{self.preferred_package_manager}."
            )
        try:
            self.unsupported_constraints_behaviour = UnsupportedConstraintsBehaviour(
                self.unsupported_constraints_behaviour
            )
        except ValueError as exc:
            raise ValueError(
                "'unsupported_constraints_behaviour' must be one of "
                f"{[value.value for value in UnsupportedConstraintsBehaviour]}."
            ) from exc

    @classmethod
    def load_user_config(cls) -> Self:
        config_file = _get_config_file()
        if config_file.is_file():
            try:
                return cls(**tomllib.loads(_get_config_file().read_text()))
            except ValueError as exc:
                raise ValueError(f"Config file '{config_file}' has errors: {exc}") from exc
        return cls()
