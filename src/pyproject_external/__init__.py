# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2023 Quansight Labs
"""
pyproject-external - Utilities to work with PEP 725 `[external]` metadata
"""

from ._config import Config # noqa
from ._external import External  # noqa
from ._registry import Registry, Ecosystems, Mapping  # noqa
from ._url import DepURL  # noqa

__all__ = [
    "Config",
    "DepURL",
    "Ecosystems",
    "External",
    "Mapping",
    "Registry",
]


def __dir__() -> list[str]:
    return __all__
