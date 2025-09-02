# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

"""
High-level API to handle `[external]` metadata tables.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field, fields
from difflib import SequenceMatcher
from hashlib import sha256
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

from dependency_groups import resolve as _resolve_dependency_groups

try:
    ExceptionGroup
except NameError:
    from exceptiongroup import ExceptionGroup

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

from ._registry import Command, Ecosystems, MappedSpec, Mapping, Registry
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
    """
    High-level dataclass API to handle `[external]` metadata tables as introduced in PEP 725.

    Each `[external]` category is available as:

    - `build_requires` / `host_requires` / `dependencies`: list of `DepURL` objects.
    - `optional_build_requires` / `optional_host_requires` / `optional_dependencies`
      / `dependency_groups`: dict that maps group names to a list of `DepURL` objects.

    Note that DepURL strings will be parsed on load and cause validation errors if not well-formed.

    The public API includes:

    - `from_pyproject_path()` / `from_pyproject_data()`: initialize `External()` from existing
      `pyproject.toml` files or payloads, respectively.
    - `to_dict()`: dump the `[external]` table as a dictionary.
    - `iter()` / `iter_optional()`: iterate over the different DepURL tables.
    - `map_dependencies()` / `map_versioned_dependencies`: Transform the `DepURL` objects into
      ecosystem-specific package identifiers, dropping or keep version constraints, respectively.
    - `install_commands()` / `query_commands()`: Generate package-manager-specific commands to
      install or query the specified external dependencies, respectively.
    - `validate()`: Perform some checks on all `DepURL` objects, including whether they are well
      formed and whether they are canonical as per the default `Registry()`.
    """

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
        """
        Instantiate `External()` from a `pyproject.toml` file by path.

        :param path: The path to the `pyproject.toml` file.
        :returns: Instance of `External`.
        """
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.from_pyproject_data(data)

    @classmethod
    def from_pyproject_data(cls, data: dict[str, Any]) -> Self:
        """
        Instantiate `External()` from a pyproject metadata contents. Only the `external`
        table is processed.

        :param data: The pyproject contents, as a dictionary.
        :returns: Instance of `External`.
        """
        try:
            return cls(**{k.replace("-", "_"): v for k, v in data["external"].items()})
        except KeyError:
            raise ValueError("Pyproject data does not have an 'external' table.")

    @property
    def registry(self) -> Registry:
        """
        An instance of the default `Registry` class. Mostly used for canonical checks.
        """
        if self._registry is None:
            self._registry = Registry.from_default()
        return self._registry

    def to_dict(
        self,
        mapped_for: str | None = None,
        package_manager: str | None = None,
        with_version: bool = True,
    ) -> dict[str, list[str] | dict[str, list[str]]]:
        """
        Dumps the `[external]` table as a dictionary, with or without mapping.

        :param mapped_for: Target ecosystem name, if any. When provided, the dictionary
            will contain the corresponding package names for each DepURL entry. If not,
            it will contain the normalized DepURL entries, as strings.
        :param package_manager: The package manager name that will further inform the
            mapping syntax for the target ecosystem. If not provided, the first one
            available in the ecosystem mapping will be used.
        :param with_version: Whether to keep or drop the version constraints when mapping
            dependencies, if supported and applicable.
        :returns: A dictionary that resembles the `[external]` table, optionally with
            mapped dependencies instead of DepURLs.
        """
        result = {}
        mapping_method = self.map_versioned_dependencies if with_version else self.map_dependencies
        for name, value in asdict(self).items():
            if not value:
                continue
            if name in self._group_keys:
                new_value = {}
                for group_name, urls in value.items():
                    if mapped_for is not None:
                        urls = mapping_method(
                            mapped_for,
                            name,
                            group_name=group_name,
                            package_manager=package_manager,
                        )
                    else:
                        urls = [url.to_string(drop_environment_marker=False) for url in urls]
                    new_value[group_name] = urls
                value = new_value
            else:
                if mapped_for is not None:
                    value = mapping_method(
                        mapped_for,
                        name,
                        package_manager=package_manager,
                    )
                else:
                    value = [url.to_string(drop_environment_marker=False) for url in value]
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
        """
        Iterate over all the required DepURLs, optionally filtering by category.

        :param categories: Which categories to iterate over. If not provided,
            all categories will be included.
        :yields: `DepURL` objects.
        """
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
        """
        Iterate over all the non-required DepURLs, optionally filtering by category and group.

        :param categories: Which categories to iterate over. If not provided,
            all categories will be included.
        :param group_name: Which group name to include from each category. If not provided,
            all gorups will be included.
        :yields: Tuples of group name and its `DepURL` objects.
        """
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

    def validate(self, canonical: bool = True, raises: bool = True) -> None:
        """
        Check whether the included DepURLs are recognized in the central registry.

        :param canonical: Check whether the included DepURLs are recognized as canonical (not
            aliases).
        :warns: Whether one or more DepURLs are not part of the central registry or canonical.
        """
        exceptions = []
        for url in chain(self.iter(), self.iter_optional()):
            try:
                self._validate_url(url, canonical=canonical, raises=raises)
            except ValueError as exc:
                exceptions.append(exc)
        if exceptions:
            raise ExceptionGroup(*exceptions)

    def _validate_url(self, url: DepURL, canonical: bool = True, raises: bool = True) -> None:
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
            msg = (
                f"Dep URL '{url}' is not recognized in the central registry. "
                f"Did you mean any of {most_similar}'?"
            )
            if raises:
                raise ValueError(msg)
            log.warning(msg)
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
                if raises:
                    raise ValueError(msg)
                log.warning(msg)

    def _map_deps_or_command_impl(
        self,
        ecosystem: str,
        categories: Iterable[ExternalKeys] | None = None,
        group_name: str | None = None,
        package_manager: str | None = None,
        return_type: Literal[
            "names", "versioned_specs", "install_commands", "query_commands"
        ] = "names",
    ) -> list[str] | list[list[str]]:
        ecosystem_names = list(Ecosystems.from_default().iter_names())
        if ecosystem not in ecosystem_names:
            raise ValueError(
                f"Ecosystem '{ecosystem}' is not a valid name. "
                f"Choose one of: {', '.join(ecosystem_names)}"
            )
        mapping: Mapping = Mapping.from_default(ecosystem)
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

        categories = categories or tuple(f.name for f in fields(self))
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
        mapped_specs = []
        for category in categories:
            required = category not in self._group_keys
            try:
                specs_type = category_to_specs_type[category]
            except KeyError:
                raise ValueError(f"Unrecognized category '{category}'.")

            if required:
                category_iterator = ((None, dep) for dep in self.iter(category))
            else:
                category_iterator = self.iter_optional(category, group_name=group_name)
            for _, dep in category_iterator:
                dep: DepURL
                dep_str = dep.to_string()
                if not dep.evaluate_environment_marker():
                    log.info(
                        "Skipping %s because its environment marker e",
                        dep.to_string(drop_environment_marker=False),
                    )
                    continue
                if specs_type == "build" and dep_str in (
                    "dep:virtual/compiler/c",
                    "dep:virtual/compiler/c++",
                    "dep:virtual/compiler/cxx",
                    "dep:virtual/compiler/cpp",
                ):
                    include_python_dev = True
                if specs := self._process_one_dep_url(
                    mapping,
                    category,
                    ecosystem,
                    dep_str,
                    specs_type,
                    required,
                ):
                    mapped_specs.extend(specs)

        if include_python_dev and (
            python_specs := self._process_one_dep_url(
                mapping,
                category,
                ecosystem,
                "dep:generic/python",
                "build",
                required=True,
            )
        ):
            mapped_specs.extend(python_specs)
        mgr = mapping.get_package_manager(package_manager)
        if return_type in ("install_commands", "query_commands"):
            return mgr.render_commands(return_type.split("_")[0], mapped_specs)
        if return_type == "versioned_specs":
            return list(chain(*(mgr.render_spec(spec) for spec in mapped_specs)))
        # return_type == "names"
        return list(dict.fromkeys([spec.name for spec in mapped_specs]))

    def _process_one_dep_url(
        self,
        mapping: Mapping,
        category: str,
        ecosystem: str,
        dep_str: str,
        specs_type: str,
        required: bool,
    ) -> list[MappedSpec]:
        for specs in mapping.iter_specs_by_id(
            dep_str,
            specs_type=specs_type,
            resolve_with_registry=self.registry,
        ):
            if specs:
                return specs
        msg = (
            f"[{category}] '{dep_str}' does not have any '{specs_type}' mappings in '{ecosystem}'!"
        )
        if next(
            mapping.iter_specs_by_id(dep_str, resolve_with_registry=self.registry),
            None,
        ):
            msg += (
                " There are mappings available in other categories, though."
                " Is this dependency in the right category?"
            )
        if required:
            raise ValueError(msg)
        log.warning(msg)
        return []

    def map_dependencies(
        self,
        ecosystem: str,
        categories: Iterable[ExternalKeys] | None = None,
        group_name: str | None = None,
        package_manager: str | None = None,
    ) -> list[str]:
        """
        Map DepURLs to their corresponding specifiers in target `ecosystem`, without version
        information (only names are returned).

        :param ecosystem: Name of the target ecosystem.
        :param categories: Which categories to map. If not provided, all categories will be mapped.
        :param group_name: Which group to map (for non-required categories). If not provided, all
            groups will be mapped.
        :param package_manager: Name of package manager that will refine the mapping syntax. If not
            provided, the first one in the mapping will be used.
        :returns: List of package names that correspond to the given DepURLs.
        """
        return self._map_deps_or_command_impl(
            ecosystem=ecosystem,
            categories=categories,
            group_name=group_name,
            package_manager=package_manager,
            return_type="names",
        )

    def map_versioned_dependencies(
        self,
        ecosystem: str,
        categories: Iterable[ExternalKeys] | None = None,
        group_name: str | None = None,
        package_manager: str | None = None,
    ) -> list[list[str]]:
        """
        Map DepURLs to their corresponding specifiers in target `ecosystem`, with version
        information.

        :param ecosystem: Name of the target ecosystem.
        :param categories: Which categories to map. If not provided, all categories will be mapped.
        :param group_name: Which group to map (for non-required categories). If not provided, all
            groups will be mapped.
        :param package_manager: Name of package manager that will refine the mapping syntax. If not
            provided, the first one in the mapping will be used.
        :returns: List of package specifiers (each a list of strings) that correspond to the given
            DepURLs.
        """
        # TODO: Pending
        return self._map_deps_or_command_impl(
            ecosystem=ecosystem,
            categories=categories,
            group_name=group_name,
            package_manager=package_manager,
            return_type="versioned_specs",
        )

    def install_commands(
        self,
        ecosystem: str,
        categories: Iterable[ExternalKeys] | None = None,
        group_name: str | None = None,
        package_manager: str | None = None,
    ) -> list[Command]:
        """
        Map DepURLs to their corresponding installation commands for the chosen
        `package_manager` in the target `ecosystem`.

        :param ecosystem: Name of the target ecosystem.
        :param categories: Which categories to process. If not provided, all categories will be mapped.
        :param group_name: Which group to process (for non-required categories). If not provided,
        all groups will be mapped.
        :param package_manager: Name of package manager that will refine the mapping syntax. If not
            provided, the first one in the mapping will be used.
        :returns: List of install commands that correspond to the given DepURLs.
        """
        return self._map_deps_or_command_impl(
            ecosystem=ecosystem,
            categories=categories,
            group_name=group_name,
            package_manager=package_manager,
            return_type="install_commands",
        )

    def query_commands(
        self,
        ecosystem: str,
        categories: Iterable[ExternalKeys] | None = None,
        group_name: str | None = None,
        package_manager: str | None = None,
    ) -> list[Command]:
        """
        Map DepURLs to their corresponding query commands for the chosen `package_manager`
        in the target `ecosystem`.

        :param ecosystem: Name of the target ecosystem.
        :param categories: Which categories to process. If not provided, all categories will be mapped.
        :param group_name: Which group to process (for non-required categories). If not provided,
        all groups will be mapped.
        :param package_manager: Name of package manager that will refine the mapping syntax. If not
            provided, the first one in the mapping will be used.
        :returns: List of query commands that correspond to the given DepURLs.
        """
        return self._map_deps_or_command_impl(
            ecosystem=ecosystem,
            categories=categories,
            group_name=group_name,
            package_manager=package_manager,
            return_type="query_commands",
        )
