# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2023 Quansight Labs
"""
pyproject-external - Utilities to work with PEP 725 `[external]` metadata
"""

from ._registry import Registry, Ecosystems, Mapping  # noqa
from ._url import DepURL  # noqa

__all__ = [
    "Registry",
    "Ecosystems",
    "Mapping",
    "DepURL",
]


def __dir__() -> list[str]:
    return __all__
