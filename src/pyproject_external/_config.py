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

    #: Which ecosystem to use by default on this system, instead of autodetected.
    preferred_ecosystem: str = ""
    #: Which package manager to use by default on this system, instead of autodetected.
    preferred_package_manager: str = ""
    #: Which mapping to use by default on this system, instead of autodetected.
    preferred_mapping: str = ""
    unsupported_constraints_behaviour: UnsupportedConstraintsBehaviour = (
        UnsupportedConstraintsBehaviour.WARN
    )

    def __post_init__(self):
        for attr in (
            "preferred_ecosystem",
            "preferred_package_manager",
            "preferred_mapping",
        ):
            if not isinstance(getattr(self, attr), str):
                raise ValueError(f"'{attr}' must be str, but found {getattr(self, attr)}.")
        if self.preferred_mapping and self.preferred_ecosystem:
            raise ValueError(
                "'preferred_mapping' cannot be set with 'preferred_ecosystem' too. Pick one."
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
