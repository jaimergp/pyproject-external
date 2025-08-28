# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

"""
Python API to interact with central registry and associated mappings
"""

from __future__ import annotations

import json
import sys
from collections import UserDict
from dataclasses import dataclass
from functools import cache
from itertools import chain
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

try:
    ExceptionGroup
except NameError:
    from exceptiongroup import ExceptionGroup

import requests
from jsonschema import Draft202012Validator, validators
from packaging.specifiers import Specifier

from ._constants import (
    DEFAULT_ECOSYSTEMS_SCHEMA_URL,
    DEFAULT_ECOSYSTEMS_URL,
    DEFAULT_MAPPING_SCHEMA_URL,
    DEFAULT_MAPPING_URL_TEMPLATE,
    DEFAULT_REGISTRY_SCHEMA_URL,
    DEFAULT_REGISTRY_URL,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any, ClassVar, Literal, TypeVar

    try:
        from typing import Self
    except ImportError:  # py 3.11+ required for Self
        from typing_extensions import Self

    from jsonschema import Validator

    _DefaultType = TypeVar("_DefaultType")
    TBuildHostRun = Literal["build", "host", "run"]
    TMultipleSpecifiers = Literal["always", "name-only", "never"]

log = getLogger(__name__)


class ValidationErrors(ExceptionGroup):
    pass


class _Validated:
    default_schema: Path | str | None
    _validator_cls = validators.create(
        meta_schema=Draft202012Validator.META_SCHEMA,
        validators=dict(Draft202012Validator.VALIDATORS),
    )

    def _validator_inst(self, path_or_url: str | None = None) -> Validator:
        if path_or_url is None and self.default_schema:
            if str(self.default_schema).startswith(("http://", "https://")):
                r = requests.get(self.default_schema)
                r.raise_for_status()
                schema = r.json()
            else:
                schema = json.loads(Path(self.default_schema).read_text())
        elif path_or_url.startswith(("http://", "https://")):
            r = requests.get(path_or_url)
            r.raise_for_status()
            schema = r.json()
        else:
            path = Path(path_or_url)
            if not path.is_absolute() and (data_path := getattr(self, "_path", None)):
                # TODO: Stop supporting relative paths and remove '._path' from _FromPathOrUrl
                data_path = Path(data_path).parent
                schema = json.loads((data_path / path).read_text())
            else:
                schema = json.loads(Path(path_or_url).read_text())
        return self._validator_cls(schema)

    def validate(self) -> None:
        schema_definition = self.data.get("$schema") or None
        errors = list(self._validator_inst(schema_definition).iter_errors(self.data))
        if errors:
            raise ValidationErrors("Validation error", errors)


class _FromPathOrUrlOrDefault:
    default_source: str

    @classmethod
    def from_default(cls, *args) -> Self:
        if "{}" in cls.default_source:
            default_source = cls.default_source.format(*args)
        else:
            default_source = cls.default_source
        if default_source.startswith(("http://", "https://")):
            return cls.from_url(default_source)
        return cls.from_path(default_source)

    @classmethod
    def from_path(cls, path: str | Path) -> Self:
        with open(path) as f:
            inst = cls(json.load(f))
        inst._path = path
        return inst

    @classmethod
    def from_url(cls, url: str) -> Self:
        r = requests.get(url)
        r.raise_for_status()
        return cls(r.json())


class Registry(UserDict, _Validated, _FromPathOrUrlOrDefault):
    """
    Dict-like interface to query a central registry document.

    In addition to all the usual dictionary API, this class adds a few iterators,
    all of them named `iter_*()`.
    """

    default_schema: str = DEFAULT_REGISTRY_SCHEMA_URL
    default_source: str = DEFAULT_REGISTRY_URL

    def iter_unique_ids(self) -> Iterable[str]:
        """
        Iterate over all unique DepURLs found in the registry.

        :yields: DepURL strings.
        """
        seen = set()
        for item in self.iter_all():
            if (id_ := item["id"]) not in seen:
                seen.add(id_)
                yield id_

    def iter_by_id(self, key: str) -> Iterable[dict[str, Any]]:
        """
        Iterate all registry definitions that match the identifier given by `key`.

        :yields: Dictionaries corresponding to registry items.
        """
        for item in self.iter_all():
            if item["id"] == key:
                yield item

    def iter_all(self) -> Iterable[dict[str, Any]]:
        """
        Iterate over all registry definitions.

        :yields: Dictionaries corresponding to registry items.
        """
        yield from self.data["definitions"]

    def iter_canonical(self) -> Iterable[dict[str, Any]]:
        """
        Iterate over all registry definitions whose identifiers are considered canonical
        (not aliased to another non-virtual identifier).

        :yields: Dictionaries corresponding to registry items.
        """
        for item in self.iter_all():
            if (
                item["id"].startswith("dep:virtual/")
                or not item.get("provides")
                or all(prov.startswith("dep:virtual/") for prov in item.get("provides"))
            ):
                yield item

    def iter_aliases(self) -> Iterable[dict[str, Any]]:
        """
        Iterate over all registry definitions that "provide" an alias to other definitions.

        :yields: Dictionaries corresponding to registry items.
        """
        for item in self.iter_all():
            if item.get("provides"):
                yield item

    def iter_generic(self) -> Iterable[dict[str, Any]]:
        """
        Iterate over all registry definitions whose type is `generic`

        :yields: Dictionaries corresponding to registry items.
        """
        for item in self.iter_all():
            if item["id"].startswith("dep:generic/"):
                yield item

    def iter_virtual(self) -> Iterable[dict[str, Any]]:
        """
        Iterate over all registry definitions whose type is `virtual`.

        :yields: Dictionaries corresponding to registry items.
        """
        for item in self.iter_all():
            if item["id"].startswith("dep:virtual/"):
                yield item


class Ecosystems(UserDict, _Validated, _FromPathOrUrlOrDefault):
    """
    Dict-like interface to query a central list of ecosystems document.

    In addition to all the usual dictionary API, this class adds a few iterators,
    all of them named `iter_*()`, and a getter.
    """

    default_schema: str = DEFAULT_ECOSYSTEMS_SCHEMA_URL
    default_source = DEFAULT_ECOSYSTEMS_URL

    # TODO: These methods might need a better API

    def iter_names(self) -> Iterable[str]:
        """
        Iterate over all the known ecosystem names.

        :yields: Ecosystem names.
        """
        yield from self.data.get("ecosystems", {})

    def iter_items(self) -> Iterable[tuple[str, dict[Literal["mapping"], str]]]:
        """
        Iterate over all the known ecosystem names, and their mapping location.

        :yields: Tuples of ecosystem name plus their definition.
        """
        yield from self.data.get("ecosystems", {}).items()

    def iter_mappings(self) -> Iterable[Mapping]:
        """
        Iterate over all the known ecosystems, returned as `Mapping` objects.

        :yields: A `Mapping` object per known ecosystem.
        """
        for _, ecosystem in self.iter_items():
            yield Mapping.from_url(ecosystem["mapping"])

    def get_mapping(self, name: str, default: _DefaultType = ...) -> Mapping | _DefaultType:
        """
        Get the `Mapping` object that corresponds to the given ecosystem `name`.

        :returns: The `Mapping` object for this name.
        """
        for item_name, ecosystem in self.iter_items():
            if name == item_name:
                return Mapping.from_url(ecosystem["mapping"])
        if default is not ...:
            return default
        raise ValueError(f"Mapping {name} cannot be found!")


class Mapping(UserDict, _Validated, _FromPathOrUrlOrDefault):
    """
    A dict-like interface for the PEP 725 mapping documents.

    These documents provide ecosystem-specific definitions for all the DepURL identifiers
    mentioned in the central registry.

    In addition to all the usual dictionary API, this class adds a few convenience properties
    to access the top-level keys, and some iterator and getter methods:

    - `iter_all()`: Iterate over all mapping entries, resolving if necessary.
    - `iter_by_id()`: Iterate over mapping entries that match this DepURL, resolving if necessary.
    - `iter_specs_by_id()`: Iterate over all the possible specifiers known for a given DepURL.
    - `iter_commands()`: Iterate over all the install or query commands that can be generated
      for the known specs of a given DepURL.
    - `get_package_manager()`: Get the instructions for a given package manager name.s
    """

    default_schema: str = DEFAULT_MAPPING_SCHEMA_URL
    default_source: str = DEFAULT_MAPPING_URL_TEMPLATE

    @property
    def name(self) -> str | None:
        "Name of the mapping."
        return self.get("name")

    @property
    def description(self) -> str | None:
        "Description of the mapping."
        return self.get("description")

    @property
    def mappings(self) -> list[dict[str, Any]]:
        "Mapping entries in the document, as a list of dictionaries."
        return self.data.get("mappings", [])

    @property
    def package_managers(self) -> list[dict[str, Any]]:
        "List of raw package manager details, as dictionaries."
        return self.data.get("package_managers", [])

    def iter_all(self, resolve_specs: bool = True) -> Iterable[dict[str, Any]]:
        """
        Iterate over all the mapping entries.

        :param resolve_specs: Whether to process `specs_from` data with the underlying specs.
            If set, all the `specs_from` items will be replaced with `specs`.
        :yields: Mapping entries, as dictionaries.
        """
        for entry in self.data["mappings"]:
            if resolve_specs:
                entry = entry.copy()
                specs = self._resolve_specs(entry)
                entry["specs"] = self._normalize_specs(specs)
                entry.pop("specs_from", None)
            yield entry

    def iter_by_id(
        self,
        key: str,
        only_mapped: bool = False,
        resolve_specs: bool = True,
        resolve_with_registry: Registry | None = None,
    ) -> Iterable[dict[str, Any]]:
        """
        Yields mapping entries matching `id` == `key`.

        :param only_mapped: Skip entries with no mapped specs.
        :param resolve_specs: Process `specs_from` entries to populate `specs`.
        :param resolve_with_registry: Process `provides` aliases with a `Registry` instance.
        :yields: Mapping entries as dictionaries.
        """
        # TODO: Deal with qualifiers?
        key = key.split("@", 1)[0]  # remove version components
        keys = {key}
        if resolve_with_registry is not None:
            keys.update(
                prov
                for alias in resolve_with_registry.iter_aliases()
                for prov in alias["provides"]
                if key == alias["id"]
            )
        for entry in self.iter_all(resolve_specs=False):
            if entry["id"] in keys:
                if resolve_specs:
                    entry = entry.copy()
                    specs = self._resolve_specs(entry)
                    entry["specs"] = self._normalize_specs(specs)
                    entry.pop("specs_from", None)
                if only_mapped:
                    try_specs_from = False
                    if specs := entry.get("specs", {}):
                        for key in "run", "host", "build":
                            if specs.get(key):
                                yield entry
                                break
                        else:
                            try_specs_from = not resolve_specs
                    if try_specs_from and entry.get("specs_from"):
                        yield entry
                else:
                    yield entry

    def _resolve_specs(self, mapping_entry: dict[str, Any]) -> list[str]:
        """
        Retrieves specs given by its `specs_from` identifier, if present.

        :returns: List of resolved specs.
        """
        if specs := mapping_entry.get("specs"):
            return specs
        if specs_from := mapping_entry.get("specs_from"):
            return self._resolve_specs(next(self.iter_by_id(specs_from)))
        return []

    @staticmethod
    def _normalize_specs(
        specs: str | list[str] | dict[str, str | list[str]],
    ) -> dict[str, list[str]]:
        """
        Normalizes `specs` entries so they are always in their full dictionary form.
        """
        if isinstance(specs, str):
            specs = {"build": [specs], "host": [specs], "run": [specs]}
        elif hasattr(specs, "items"):  # assert all fields are present as lists
            for key in "build", "host", "run":
                specs.setdefault(key, [])
                if isinstance(specs[key], str):
                    specs[key] = [specs[key]]
        else:  # list
            specs = {"build": specs, "host": specs, "run": specs}
        return specs

    def get_package_manager(self, name: str) -> PackageManager:
        """
        Finds package manager by `name`, if present.

        :param name: Name of the package manager.
        :returns: A `PackageManager` instance.
        """
        for manager in self.data["package_managers"]:
            if manager["name"] == name:
                return PackageManager.from_mapping_entry(manager)
        raise ValueError(f"Could not find '{name}' in {self.data['package_managers']}")

    def iter_specs_by_id(
        self,
        dep_url: str,
        specs_type: TBuildHostRun | Iterable[TBuildHostRun] | None = None,
        **kwargs,
    ) -> Iterable[list[MappedSpec]]:
        """
        Yields all the specs found for the identifier `dep_url` to be consumed by a command line
        application.

        :param dep_url: The DepURL identifier to obtain specs from.
        :param package_manager: The name of the package manager that will provide the command line
            argument syntax.
        :param specs_type: Which category of specs to return, or all of them.
        :param with_version: Whether to transform the version constraints, if available and
            applicable.
        :yields: A list of lists of strings. Each `dep_url` may correspond to more than one
            package name. Each package name may be expressed by more than one command line
            argument. Hence the double nested list.
        """
        if "@" in dep_url and not dep_url.startswith("dep:virtual/"):
            # TODO: Virtual versions are not implemented
            # (e.g. how to map a language standard to a concrete version)
            dep_url, version = dep_url.split("@", 1)
        else:
            version = ""
        if specs_type is None:
            specs_type = ("build", "host", "run")
        elif isinstance(specs_type, str):
            specs_type = (specs_type,)
        for entry in self.iter_by_id(dep_url, **kwargs):
            specs = list(dict.fromkeys(s for key in specs_type for s in entry["specs"][key]))
            yield [MappedSpec(name, version) for name in specs]

    def iter_commands(
        self,
        command_type: Literal["install", "query"],
        dep_url: str,
        package_manager: str,
        specs_type: TBuildHostRun | Iterable[TBuildHostRun] | None = None,
        **kwargs,
    ) -> Iterable[list[Command]]:
        """
        Yields `command_type` Command objects for the identifier `dep_url` and `package_manager`.

        :param command_type: Which type of command to generate: install or query.
        :param dep_url: The DepURL to install.
        :param package_manager: Name of the package manager that will provide the command syntax.
        :param specs_type: Which category of specs to process, or all of them.
        :yields: List of Commands necessary to install the specs of a given mapping entry.
            If the package manager allows multiple specifiers, this list will only contain
            one command. Otherwise, the list will contain one command per package.
        """
        mgr = self.get_package_manager(package_manager)
        for specs in self.iter_specs_by_id(dep_url, specs_type, **kwargs):
            yield mgr.render_commands(command_type, specs)


@dataclass
class CommandInstructions:
    """
    Instructions to build a certain command.
    """

    command_template: list[str]
    requires_elevation: bool
    multiple_specifiers: TMultipleSpecifiers

    def __post_init__(self):
        if len([arg for arg in self.command_template if arg == "{}"]) != 1:
            raise ValueError("'command_template' must include one (and one only) `'{}'` item.")
        if self.multiple_specifiers not in ("always", "name-only", "never"):
            raise ValueError(
                "'multiple_specifiers' must be one of: 'always', 'name-only', 'never'"
            )

    def render_template(self) -> list[str]:
        """
        Processes the command template to inject the required elevation logic, if applicable.

        :returns: List of arguments plus the template placeholder
        """
        template = []
        if self.requires_elevation:
            # TODO: Add a system to infer type of elevation required (sudo vs Windows AUC)
            if sys.platform.startswith("win"):
                template.append("runas")
            else:
                template.append("sudo")
        template.extend(self.command_template)
        return template


@dataclass
class MappedSpec:
    """
    A dataclass storing the name and, optionally, version constraints of a mapped package specifier.
    """

    name: str
    version: str

    def __post_init__(self):
        if not self.name:
            raise ValueError("'name' cannot be empty.")

    def __hash__(self) -> int:
        return hash(f"{self.name}-{self.version}")


@dataclass
class Command:
    """
    A dataclass representing a templated (with one item being a `{}` placeholder) command,
    with its arguments stored separately."""

    template: list[str]
    arguments: list[str]

    def __post_init__(self):
        if len([arg for arg in self.template if arg == "{}"]) != 1:
            raise ValueError("'template' must include one (and one only) `'{}'` item.")
        if not self.arguments:
            raise ValueError("'arguments' cannot be empty.")

    @classmethod
    def merge(cls, *commands: Self) -> Self:
        """
        Merge several Command instances into a single one, with all their arguments
        concatenated in order.

        :param commands: Command instances to merge.
        :returns: Command instance with all arguments concatenated.
        """
        if len(commands) == 1:
            return cls(commands[0].template, commands[0].arguments)
        if not all(commands[0].template == command.template for command in commands[1:]):
            raise ValueError("All Command instances must have the same template.")
        return cls(
            template=commands[0].template,
            arguments=[arg for command in commands for arg in command.arguments],
        )

    def render(self) -> list[str]:
        """
        Injects `arguments` in the position indicated by the `{}` placeholder item in `template`.

        :returns: List of arguments ready to be consumed by `subprocess.run`-like APIs.
        """
        cmd = []
        for arg in self.template:
            if arg == "{}":
                cmd.extend(self.arguments)
            else:
                cmd.append(arg)
        return cmd

    def __iter__(self) -> Iterable[str]:
        """
        Iterate over the rendered command.

        :yields: Arguments in the rendered command.
        """
        yield from self.render()


@dataclass
class PackageManager:
    """
    A dataclass representing a `Mapping["package_managers"]` entry.
    """

    name: str
    install: CommandInstructions
    query: CommandInstructions
    name_only_syntax: list[str]
    exact_version_syntax: list[str] | None
    version_ranges_syntax: list[str] | None
    version_ranges_and: str | None
    version_ranges_equal: str | None
    version_ranges_greater_than: str | None
    version_ranges_greater_than_equal: str | None
    version_ranges_less_than: str | None
    version_ranges_less_than_equal: str | None
    version_ranges_not_equal: str | None

    default_multiple_specifiers_install: ClassVar[TMultipleSpecifiers] = "always"
    default_multiple_specifiers_query: ClassVar[TMultipleSpecifiers] = "never"
    default_requires_elevation: ClassVar[bool] = False

    @classmethod
    def from_mapping_entry(cls, entry: dict[str, Any]) -> Self:
        """
        Instantiate `PackageManager` from a dict entry found in a `Mapping["package_managers"]`.

        :param entry: A dictionary as found in the `Mapping["package_managers"]` list.
        :returns: A `PackageManager` instance.
        """
        version_ranges = entry["specifier_syntax"].get("version_ranges") or {}
        return cls(
            name=entry["name"],
            install=CommandInstructions(
                command_template=entry["commands"]["install"]["command"],
                multiple_specifiers=entry["commands"]["install"].get(
                    "multiple_specifiers",
                    cls.default_multiple_specifiers_install,
                ),
                requires_elevation=entry["commands"]["install"].get(
                    "requires_elevation",
                    cls.default_requires_elevation,
                ),
            ),
            query=CommandInstructions(
                command_template=entry["commands"]["query"]["command"],
                multiple_specifiers=entry["commands"]["query"].get(
                    "multiple_specifiers",
                    cls.default_multiple_specifiers_query,
                ),
                requires_elevation=entry["commands"]["query"].get(
                    "requires_elevation",
                    cls.default_requires_elevation,
                ),
            ),
            name_only_syntax=entry["specifier_syntax"]["name_only"],
            exact_version_syntax=entry["specifier_syntax"]["exact_version"],
            version_ranges_syntax=version_ranges.get("syntax"),
            version_ranges_and=version_ranges.get("and"),
            version_ranges_equal=version_ranges.get("equal"),
            version_ranges_greater_than=version_ranges.get("greater_than"),
            version_ranges_greater_than_equal=version_ranges.get("greater_than_equal"),
            version_ranges_less_than=version_ranges.get("less_than"),
            version_ranges_less_than_equal=version_ranges.get("less_than_equal"),
            version_ranges_not_equal=version_ranges.get("not_equal"),
        )

    def render_commands(
        self, command: Literal["install", "query"], specs: Iterable[MappedSpec]
    ) -> list[Command]:
        """
        Build the commands necessary to process the `specs` list.

        :param command: Type of command to generate (`install` or `query`).
        :param specs: The `MappedSpec` objects to process.
        :returns: A list of `Command` objects. If the package manager supports multiple
            specifiers per command, this list will only contain one `Command`. Otherwise,
            it will contain one `Command` per `MappedSpec`.
        """
        instructions: CommandInstructions = getattr(self, command)
        all_args: list[list[str]] = []
        versioned_args: list[list[str]] = []
        unversioned_args: list[list[str]] = []
        seen = set()
        for spec in specs:
            if spec in seen:
                continue
            seen.add(spec)
            args = self.render_spec(spec)
            if not args:
                continue
            all_args.append(args)
            if spec.version:
                versioned_args.append(args)
            else:
                unversioned_args.append(args)
        if instructions.multiple_specifiers == "always":
            return [Command(instructions.render_template(), list(chain(*all_args)))]
        cmds = []
        if instructions.multiple_specifiers == "name-only":
            if unversioned_args:
                cmds.append(
                    Command(
                        instructions.render_template(),
                        list(chain(*unversioned_args)),
                    )
                )
            for args in versioned_args:
                cmds.append(Command(instructions.render_template(), args))
            return cmds
        for args in all_args:
            cmds.append(Command(instructions.render_template(), args))
        return cmds

    def render_spec(self, spec: MappedSpec, with_version: bool = True) -> list[str]:
        """
        Given a MappedSpec, generate the list of arguments for this package manager. We need
        to account for name-only, exact-version-only and ranges-supported cases. The first
        two are simple templates, the third one is a bit more involved.

        The templates are given the package manager info, and are all a list of strings.

        - Name-only: Replace `{name}` in all items.
        - Exact-version-only: Replace `{name}` and `{version}` in all items. Need
          to ensure the version passed is NOT a range.
        - Ranges: Parse the version into constraints (they'll come comma-separated if more
          than one), and for each constraint parse the operator and version value. Pick the
          operator template and replace `{op}` and `{version}`. Then, if `and` is a string,
          join them. Pick the `syntax` template and replace `{name}` and `{ranges}` for each
          item in the list. If `and` was None, then "explode" the items containing `{ranges}`
          once per parsed constraint.

        Note: Exploded constraints require multiple-specifiers=always.
        """
        if not with_version or not spec.version:
            return [arg.format(name=spec.name) for arg in self.name_only_syntax]

        if not spec.version.startswith(("=", ">", "<", "!", "~")):
            version = f"==={spec.version}"
        else:
            version = spec.version
        constraints = version.split(",")
        if len(constraints) == 1 and (constraint := Specifier(constraints[0])).operator == "===":
            # exact version
            if not self.exact_version_syntax:
                raise ValueError(
                    "This package manager does not support exact version constraints."
                    f"Spec name '{spec.name}' and version '{spec.version}'."
                )
            return [
                item.format(name=spec.name, version=constraint.version)
                for item in self.exact_version_syntax
            ]

        # This is range-versions territory

        if not self.version_ranges_syntax:
            raise ValueError(
                "This package manager does not support version range constraints. "
                f"Spec name '{spec.name}' and version '{spec.version}'."
            )

        mapped_constraints = []
        for constraint in constraints:
            constraint = Specifier(constraint)
            self._validate_specifier(spec.name, constraint)
            constraint_template = getattr(
                self, f"version_ranges_{constraint._operators[constraint.operator]}"
            )
            if constraint_template is None:
                raise ValueError(f"Constraint '{constraint}' in '{spec.name}' is not supported.")
            mapped_constraint = constraint_template.format(
                name=spec.name, version=constraint.version
            )
            mapped_constraints.append(mapped_constraint)
        result = []
        if self.version_ranges_and is None:
            for item in self.version_ranges_syntax:
                for range_ in mapped_constraints:
                    result.append(item.format(name=spec.name, ranges=range_))
        else:
            ranges = self.version_ranges_and.join(mapped_constraints)
            for item in self.version_ranges_syntax:
                result.append(item.format(name=spec.name, ranges=ranges))
        return result

    def _validate_specifier(self, name: str, specifier: Specifier) -> None:
        not_supported = ("~=", "===", "!=")
        if specifier.operator in not_supported:
            raise ValueError(
                f"Package '{name}' has invalid operator '{specifier.operator}' "
                f"in constraint '{specifier}'."
            )
        if "*" in specifier.version:
            raise ValueError(
                f"Package '{name}' has invalid operator '*' in constraint '{specifier}'."
            )


@cache
def default_ecosystems() -> Ecosystems:
    return Ecosystems.from_default()


@cache
def remote_mapping(ecosystem_or_url: str) -> Mapping:
    if ecosystem_or_url.startswith(("http://", "https://")):
        return Mapping.from_url(ecosystem_or_url)
    return Mapping.from_default(ecosystem_or_url)
