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
    from typing import Any, Literal, TypeAlias

    try:
        from typing import Self

        _TExternal: TypeAlias = Self
    except ImportError:  # py 3.11+ required for Self
        from typing import TypeVar

        _TExternal: TypeVar = TypeVar("TExternal", bound="External")

from ._registry import Ecosystems, Mapping
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
            setattr(self, name, [DepURL.from_string(url) for url in urls])

    @classmethod
    def from_pyproject_path(cls, path: os.PathLike | Path) -> _TExternal:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.from_pyproject_data(data)

    @classmethod
    def from_pyproject_data(cls, data: dict[str, Any]) -> Self:
        try:
            return cls(**{k.replace("-", "_"): v for k, v in data["external"].items()})
        except KeyError:
            raise ValueError("Pyproject data does not have an 'external' table.")

    def _map_install_deps_impl(
        self,
        ecosystem: str,
        key: Literal[
            "build_requires",
            "host_requires",
            "dependencies",
            "optional_build_requires",
            "optional_host_requires",
            "optional_dependencies",
        ]
        | None = None,
        package_manager: str | None = None,
        as_install_command: bool = False,
    ) -> list[str]:
        ecosystem_names = list(Ecosystems.from_default().iter_all())
        if ecosystem not in ecosystem_names:
            raise ValueError(
                f"Ecosystem '{ecosystem}' is not a valid name. "
                f"Choose one of: {', '.join(ecosystem_names)}"
            )
        mapping = Mapping.from_default(ecosystem)
        package_manager_names = [mgr["name"] for mgr in mapping.package_managers]
        if package_manager is None:
            if package_manager_names == 1:
                package_manager = package_manager_names[0]
            else:
                raise ValueError(f"Choose a package manager: {package_manager_names}")
        elif package_manager not in package_manager_names:
            raise ValueError(
                f"package_manager '{package_manager}' not recognized. "
                f"Choose one of {package_manager_names}."
            )

        if key is None:
            specs_type = None
            required = True
        else:
            required = "optional" not in key
            if "build" in key:
                specs_type = "build"
            elif "host" in key:
                specs_type = "host"
            elif "dependencies" in key:
                specs_type = "run"
            else:
                raise ValueError(f"Unrecognized key '{key}'.")

        all_specs = []
        for dep in getattr(self, key):
            dep: DepURL
            for specs in mapping.iter_specs_by_id(
                dep.to_string(), package_manager, specs_type=specs_type
            ):
                all_specs.extend(specs)
                break
            else:
                if required:
                    raise ValueError(f"'{dep.to_string()}' has no mapped deps in {ecosystem}!")

        if as_install_command:
            return mapping.build_install_command(
                mapping.get_package_manager(package_manager), all_specs
            )
        return all_specs

    def map_dependencies(
        self,
        ecosystem: str,
        key: Literal[
            "build_requires",
            "host_requires",
            "dependencies",
            "optional_build_requires",
            "optional_host_requires",
            "optional_dependencies",
        ]
        | None = None,
        package_manager: str | None = None,
    ) -> list[str]:
        return self._map_install_deps_impl(
            ecosystem=ecosystem,
            key=key,
            package_manager=package_manager,
            as_install_command=False,
        )

    def install_command(
        self,
        ecosystem: str,
        key: Literal[
            "build_requires",
            "host_requires",
            "dependencies",
            "optional_build_requires",
            "optional_host_requires",
            "optional_dependencies",
        ]
        | None = None,
        package_manager: str | None = None,
    ) -> list[str]:
        return self._map_install_deps_impl(
            ecosystem=ecosystem,
            key=key,
            package_manager=package_manager,
            as_install_command=True,
        )
