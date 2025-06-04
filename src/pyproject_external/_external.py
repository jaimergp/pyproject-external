from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import tomllib
except ImportError:
    import tomli as tomllib

if TYPE_CHECKING:
    from typing import Any, Iterable, Literal, TypeAlias

    try:
        from typing import Self

        _TExternal: TypeAlias = Self
    except ImportError:  # py 3.11+ required for Self
        from typing import TypeVar

        _TExternal: TypeVar = TypeVar("TExternal", bound="External")

from ._registry import Ecosystems, Mapping, Registry
from ._url import DepURL

log = logging.getLogger(__name__)


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
            setattr(self, "_raw_" + name, urls)
            setattr(self, name, [DepURL.from_string(url) for url in urls])

    @classmethod
    def from_pyproject_path(cls, path: os.PathLike | Path) -> _TExternal:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.from_pyproject_data(data)

    @classmethod
    def from_pyproject_data(cls, data: dict[str, Any]) -> _TExternal:
        try:
            return cls(**{k.replace("-", "_"): v for k, v in data["external"].items()})
        except KeyError:
            raise ValueError("Pyproject data does not have an 'external' table.")

    def to_dict(
        self, mapped_for: str | None = None, package_manager: str | None = None
    ) -> dict[str, list[DepURL]]:
        result = {}
        for name, value in asdict(self).items():
            if not value:
                continue
            if mapped_for is not None:
                value = self.map_dependencies(mapped_for, name, package_manager=package_manager)
            else:
                value = [url.to_string() for url in value]
            result[name] = value
        return {"external": result}

    def iter(
        self,
        *categories: Literal[
            "build_requires",
            "host_requires",
            "dependencies",
            "optional_build_requires",
            "optional_host_requires",
            "optional_dependencies",
        ],
    ) -> Iterable[str]:
        if not categories:
            categories = (
                "build_requires",
                "host_requires",
                "dependencies",
                "optional_build_requires",
                "optional_host_requires",
                "optional_dependencies",
            )
        for category in categories:
            for dependency in getattr(self, category):
                yield dependency

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
        ecosystem_names = list(Ecosystems.from_default().iter_names())
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

        categories = (
            (key,)
            if key
            else (
                "build_requires",
                "host_requires",
                "dependencies",
                "optional_build_requires",
                "optional_host_requires",
                "optional_dependencies",
            )
        )
        all_specs = []
        include_python_dev = False
        for category in categories:
            required = "optional" not in category
            if "build" in category:
                specs_type = "build"
            elif "host" in category:
                specs_type = "host"
            elif "dependencies" in category:
                specs_type = "run"
            else:
                raise ValueError(f"Unrecognized category '{category}'.")

            for dep in getattr(self, category):
                dep: DepURL
                dep_str = dep.to_string()
                if specs_type == "build" and dep_str in (
                    "dep:virtual/compiler/c",
                    "dep:virtual/compiler/c++",
                    "dep:virtual/compiler/cxx",
                    "dep:virtual/compiler/cpp",
                ):
                    include_python_dev = True
                for specs in mapping.iter_specs_by_id(
                    dep_str, package_manager, specs_type=specs_type
                ):
                    if not specs:
                        continue
                    all_specs.extend(specs)
                    break
                else:
                    msg = f"[{category}] '{dep_str}' does not have any mappings in '{ecosystem}'!"
                    if required:
                        raise ValueError(msg)
                    else:
                        log.warning(msg)

        if include_python_dev:
            # TODO: handling of non-default Python installs isn't done here,
            # this adds the python-dev/devel package corresponding to the
            # default Python version of the distro.
            all_specs.extend(
                next(iter(mapping.iter_by_id("dep:generic/python")))["specs"]["build"]
            )
        all_specs = list(dict.fromkeys(all_specs))

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

    def validate(self, registry: bool = True, canonical: bool = True) -> None:
        if not registry and not canonical:
            return
        default_registry = Registry.from_default()
        for url in self.iter():
            if registry and url not in default_registry.iter_unique_urls():
                log.warning(f"Dep URL {url} is not recognized in the central registry.")
            if canonical:
                canonical_entries = {item["id"] for item in default_registry.iter_canonical()}
                if url not in canonical_entries:
                    for d in default_registry.iter_by_id(url):
                        if provides := d.get("provides"):
                            references = ", ".join(provides)
                            break
                    else:
                        references = None
                    msg = f"Dep URL {url} is not using a canonical reference."
                    if references:
                        msg += f" Try with one of: {references}."
                    log.warning(msg)
