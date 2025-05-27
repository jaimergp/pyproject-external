from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import tomllib
except ImportError:
    import tomli as tomllib

if TYPE_CHECKING:
    from typing import Any

    try:
        from typing import Self as _TExternal
    except ImportError:  # py 3.11+ required for Self
        from typing import TypeVar

        _TExternal: TypeVar = TypeVar("TExternal", bound="External")

from ._url import DepURL


@dataclass
class External:
    build_requires: list[DepURL] = field(default_factory=list)
    host_requires: list[DepURL] = field(default_factory=list)
    dependencies: list[DepURL] = field(default_factory=list)
    optional_build_requires: list[DepURL] = field(default_factory=list)
    optional_host_requires: list[DepURL] = field(default_factory=list)
    optional_dependencies: list[DepURL] = field(default_factory=list)

    def __post_init__(self):
        for name, urls in asdict(self).items():
            # coerce to DepURL and validate
            setattr(self, name, [DepURL.from_string(url.replace("dep:", "pkg:")) for url in urls])

    @classmethod
    def from_pyproject_path(cls, path: os.PathLike | Path) -> _TExternal:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.from_pyproject_data(data)

    @classmethod
    def from_pyproject_data(cls, data: dict[str, Any]) -> _TExternal:
        try:
            return cls(**data["external"])
        except KeyError:
            raise ValueError("Pyproject data does not have an 'external' table.")
