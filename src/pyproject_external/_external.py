from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field, fields
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

from dependency_groups import resolve as _resolve_dependency_groups

try:
    import tomllib
except ImportError:
    import tomli as tomllib

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any, Literal, TypeAlias

    try:
        from typing import Self
    except ImportError:  # py 3.11+ required for Self
        from typing_extensions import Self

    ExternalKeys: TypeAlias = Literal[
        "build_requires",
        "host_requires",
        "dependencies",
        "optional_build_requires",
        "optional_host_requires",
        "optional_dependencies",
        "dependency_groups",
    ]

from ._registry import Ecosystems, Mapping, Registry
from ._url import DepURL

log = logging.getLogger(__name__)


def _resolve_dependency_groups_with_hashed_deps(
    groups: dict[str, list[str | dict[str, Any]]],
) -> dict[str, list[str]]:
    """
    The dependency_groups.resolve() logic expects valid Python requirements,
    so our `dep:` URLs will not pass that validation. We take their sha256 hash
    (which happen to be valid Python specifiers) before passing them to the resolver,
    and then convert the hash back to the original string.
    """
    patched_groups = {}
    hashed_deps = {}
    for group_name, group in groups.items():
        patched_group = []
        for maybe_dep in group:
            if isinstance(maybe_dep, str):
                hashed_dep = sha256(maybe_dep.encode()).hexdigest()
                hashed_deps[hashed_dep] = maybe_dep
                patched_group.append(hashed_dep)
            else:
                patched_group.append(maybe_dep)
        patched_groups[group_name] = patched_group
    return {
        group_name: [
            hashed_deps[dep] for dep in _resolve_dependency_groups(patched_groups, group_name)
        ]
        for group_name in patched_groups
    }


@dataclass
class External:
    build_requires: list[DepURL] = field(default_factory=list)
    host_requires: list[DepURL] = field(default_factory=list)
    dependencies: list[DepURL] = field(default_factory=list)
    optional_build_requires: dict[str, list[DepURL]] = field(default_factory=dict)
    optional_host_requires: dict[str, list[DepURL]] = field(default_factory=dict)
    optional_dependencies: dict[str, list[DepURL]] = field(default_factory=dict)
    dependency_groups: dict[str, list[DepURL] | dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        self._registry = None
        self._group_keys = (
            "optional_build_requires",
            "optional_host_requires",
            "optional_dependencies",
            "dependency_groups",
        )
        for name, urls_or_group in asdict(self).items():
            if name in self._group_keys:
                if name == "dependency_groups":
                    flattened = _resolve_dependency_groups_with_hashed_deps(urls_or_group)
                else:
                    flattened = urls_or_group
                coerced = {
                    group_name: [DepURL.from_string(url) for url in urls]
                    for group_name, urls in flattened.items()
                }
                setattr(self, name, coerced)
            else:
                # coerce to DepURL and validate
                setattr(self, name, [DepURL.from_string(url) for url in urls_or_group])

    @classmethod
    def from_pyproject_path(cls, path: os.PathLike | Path) -> Self:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.from_pyproject_data(data)

    @classmethod
    def from_pyproject_data(cls, data: dict[str, Any]) -> Self:
        try:
            return cls(**{k.replace("-", "_"): v for k, v in data["external"].items()})
        except KeyError:
            raise ValueError("Pyproject data does not have an 'external' table.")

    @property
    def registry(self) -> Registry:
        if self._registry is None:
            self._registry = Registry.from_default()
        return self._registry

    def to_dict(
        self, mapped_for: str | None = None, package_manager: str | None = None
    ) -> dict[str, list[DepURL]]:
        result = {}
        for name, value in asdict(self).items():
            if not value:
                continue
            if name in self._group_keys:
                new_value = {}
                for group_name, urls in value.items():
                    if mapped_for is not None:
                        urls = self.map_dependencies(
                            mapped_for,
                            name,
                            group_name=group_name,
                            package_manager=package_manager,
                        )
                    else:
                        urls = [url.to_string() for url in urls]
                    new_value[group_name] = urls
                value = new_value
            else:
                if mapped_for is not None:
                    value = self.map_dependencies(
                        mapped_for,
                        name,
                        package_manager=package_manager,
                    )
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
        ],
    ) -> Iterable[DepURL]:
        if not categories:
            categories = (
                "build_requires",
                "host_requires",
                "dependencies",
            )
        for category in categories:
            yield from getattr(self, category)

    def iter_optional(
        self,
        *categories: Literal[
            "optional_build_requires",
            "optional_host_requires",
            "optional_dependencies",
            "dependency_groups",
        ],
        group_name: str | None = None,
    ) -> Iterable[tuple[str, DepURL]]:
        if not categories:
            categories = (
                "optional_build_requires",
                "optional_host_requires",
                "optional_dependencies",
                "dependency_groups",
            )

        for category in categories:
            if group_name is not None:
                for dependency in getattr(self, category).get(group_name, ()):
                    yield group_name, dependency
            else:
                for name, dependencies in getattr(self, category).items():
                    for dependency in dependencies:
                        yield name, dependency

    def _map_install_deps_impl(
        self,
        ecosystem: str,
        key: ExternalKeys | None = None,
        group_name: str | None = None,
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

        categories = (key,) if key else tuple(f.name for f in fields(self))
        all_specs = []
        include_python_dev = False
        category_to_specs_type = {
            "build_requires": "build",
            "host_requires": "host",
            "dependencies": "run",
            "optional_build_requires": "build",
            "optional_host_requires": "host",
            "optional_dependencies": "run",
            "dependency_groups": "run",
        }
        for category in categories:
            required = category not in self._group_keys
            try:
                specs_type = category_to_specs_type[category]
            except KeyError:
                raise ValueError(f"Unrecognized category '{category}'.")

            if required:
                iterator = ((None, dep) for dep in self.iter(category))
            else:
                iterator = self.iter_optional(category, group_name=group_name)
            for _, dep in iterator:
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
                    dep_str,
                    package_manager,
                    specs_type=specs_type,
                    resolve_with_registry=self.registry,
                ):
                    if not specs:
                        continue
                    all_specs.extend(specs)
                    break
                else:
                    msg = (
                        f"[{category}] '{dep_str}' does not have any "
                        f"'{specs_type}' mappings in '{ecosystem}'!"
                    )
                    if next(
                        mapping.iter_specs_by_id(
                            dep_str, package_manager, resolve_with_registry=self.registry
                        ),
                        None,
                    ):
                        msg += (
                            " There are mappings available in other categories, though."
                            " Is this dependency in the right category?"
                        )
                    if required:
                        raise ValueError(msg)
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
        key: ExternalKeys | None = None,
        group_name: str | None = None,
        package_manager: str | None = None,
    ) -> list[str]:
        return self._map_install_deps_impl(
            ecosystem=ecosystem,
            key=key,
            group_name=group_name,
            package_manager=package_manager,
            as_install_command=False,
        )

    def install_command(
        self,
        ecosystem: str,
        key: ExternalKeys | None = None,
        group_name: str | None = None,
        package_manager: str | None = None,
    ) -> list[str]:
        return self._map_install_deps_impl(
            ecosystem=ecosystem,
            key=key,
            group_name=group_name,
            package_manager=package_manager,
            as_install_command=True,
        )

    def validate(self, canonical: bool = True) -> None:
        for url in self.iter():
            self._validate_url(url, canonical=canonical)

    def _validate_url(self, url: DepURL, canonical: bool = True) -> None:
        unique_urls = set()
        unique_strs = []
        for id_ in self.registry.iter_unique_ids():
            unique_strs.append(id_)
            unique_urls.add(DepURL.from_string(id_))
        if url not in unique_urls:
            most_similar = sorted(
                unique_strs,
                key=lambda i: SequenceMatcher(None, str(url), i).ratio(),
                reverse=True,
            )[:5]
            log.warning(
                f"Dep URL '{url}' is not recognized in the central registry. "
                f"Did you mean any of {most_similar}'?"
            )
            return
        if canonical:
            canonical_entries = {item["id"] for item in self.registry.iter_canonical()}
            if str(url) not in canonical_entries:
                for d in self.registry.iter_by_id(url):
                    if provides := d.get("provides"):
                        references = ", ".join(provides)
                        break
                else:
                    references = None
                msg = f"Dep URL '{url}' is not using a canonical reference."
                if references:
                    msg += f" Try with one of: {references}."
                log.warning(msg)
