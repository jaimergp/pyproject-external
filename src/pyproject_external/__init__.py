# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2023 Quansight Labs
"""
pyproject-external - Utilities to work with PEP 725 `[external]` metadata
"""

from ._external import External  # noqa
from ._registry import Registry, Ecosystems, Mapping, default_ecosystems, remote_mapping  # noqa
from ._system import find_ecosystem_for_package_manager, detect_ecosystem_and_package_manager
from ._url import DepURL  # noqa

__all__ = [
    "DepURL",
    "Ecosystems",
    "External",
    "Mapping",
    "Registry",
    "find_ecosystem_for_package_manager",
    "detect_ecosystem_and_package_manager",
    "default_ecosystems",
    "remote_mapping",
]


def __dir__() -> list[str]:
    return __all__
