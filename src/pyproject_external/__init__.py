# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2023 Quansight Labs
"""
pyproject-external - Utilities to work with PEP 725 `[external]` metadata
"""

from ._config import Config  # noqa
from ._external import External  # noqa
from ._registry import Registry, Ecosystems, Mapping, default_ecosystems, remote_mapping  # noqa
from ._system import (  # noqa
    find_ecosystem_for_package_manager,
    detect_ecosystem_and_package_manager,
    activated_conda_env,
)
from ._url import DepURL  # noqa
from ._version import __version__

__all__ = [
    "__version__",
    "Config",
    "DepURL",
    "Ecosystems",
    "External",
    "Mapping",
    "Registry",
    "activated_conda_env",
    "find_ecosystem_for_package_manager",
    "detect_ecosystem_and_package_manager",
    "default_ecosystems",
    "remote_mapping",
]


def __dir__() -> list[str]:
    return __all__
