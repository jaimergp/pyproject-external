# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

"""
Python API to interact with central registry and associated mappings
"""

from __future__ import annotations

import json
from collections import UserDict
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

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
    from typing import Any, Literal, TypeVar

    try:
        from typing import Self
    except ImportError:  # py 3.11+ required for Self
        from typing_extensions import Self

    from jsonschema import Validator

    _DefaultType = TypeVar("_DefaultType")
    TBuildHostRun = Literal["build", "host", "run"]


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
            msg = "\n".join(errors)
            raise ValueError(f"Validation error: {msg}")


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
    default_schema: str = DEFAULT_REGISTRY_SCHEMA_URL
    default_source: str = DEFAULT_REGISTRY_URL

    def iter_unique_ids(self) -> Iterable[str]:
        seen = set()
        for item in self.iter_all():
            if (id_ := item["id"]) not in seen:
                seen.add(id_)
                yield id_

    def iter_by_id(self, key: str) -> Iterable[dict[str, Any]]:
        for item in self.iter_all():
            if item["id"] == key:
                yield item

    def iter_all(self) -> Iterable[dict[str, Any]]:
        yield from self.data["definitions"]

    def iter_canonical(self) -> Iterable[dict[str, Any]]:
        for item in self.iter_all():
            if (
                item["id"].startswith("dep:virtual/")
                or not item.get("provides")
                or all(prov.startswith("dep:virtual/") for prov in item.get("provides"))
            ):
                yield item

    def iter_aliases(self) -> Iterable[dict[str, Any]]:
        for item in self.iter_all():
            if item.get("provides"):
                yield item

    def iter_generic(self) -> Iterable[dict[str, Any]]:
        for item in self.iter_all():
            if item["id"].startswith("dep:generic/"):
                yield item

    def iter_virtual(self) -> Iterable[dict[str, Any]]:
        for item in self.iter_all():
            if item["id"].startswith("dep:virtual/"):
                yield item


class Ecosystems(UserDict, _Validated, _FromPathOrUrlOrDefault):
    default_schema: str = DEFAULT_ECOSYSTEMS_SCHEMA_URL
    default_source = DEFAULT_ECOSYSTEMS_URL

    # TODO: These methods might need a better API

    def iter_names(self) -> Iterable[tuple[str, dict[Literal["mapping"], str]]]:
        yield from self.data.get("ecosystems", {})

    def iter_items(self) -> Iterable[tuple[str, dict[Literal["mapping"], str]]]:
        yield from self.data.get("ecosystems", {}).items()

    def iter_mappings(self) -> Iterable[Mapping]:
        for name, ecosystem in self.iter_items():
            yield Mapping.from_url(ecosystem["mapping"])

    def get_mapping(self, name: str, default: _DefaultType = ...) -> Mapping | _DefaultType:
        for item_name, ecosystem in self.iter_items():
            if name == item_name:
                return Mapping.from_url(ecosystem["mapping"])
        if default is not ...:
            return default
        raise ValueError(f"Mapping {name} cannot be found!")


class Mapping(UserDict, _Validated, _FromPathOrUrlOrDefault):
    default_schema: str = DEFAULT_MAPPING_SCHEMA_URL
    default_source: str = DEFAULT_MAPPING_URL_TEMPLATE
    default_operator_mapping = {
        "and": ",",
        "separator": "",
        **{v: k for (k, v) in Specifier._operators.items()},
    }

    @property
    def name(self) -> str | None:
        return self.get("name")

    @property
    def description(self) -> str | None:
        return self.get("description")

    @property
    def mappings(self) -> list[dict[str, Any]]:
        return self.data.get("package_managers", [])

    @property
    def package_managers(self) -> list[dict[str, Any]]:
        return self.data.get("package_managers", [])

    def iter_all(self, resolve_specs: bool = True) -> Iterable[dict[str, Any]]:
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
        if specs := mapping_entry.get("specs"):
            return specs
        if specs_from := mapping_entry.get("specs_from"):
            return self._resolve_specs(next(self.iter_by_id(specs_from)))
        return []

    @staticmethod
    def _normalize_specs(
        specs: str | list[str] | dict[str, str | list[str]],
    ) -> dict[str, list[str]]:
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

    def get_package_manager(self, name: str) -> dict[str, Any]:
        for manager in self.data["package_managers"]:
            if manager["name"] == name:
                return manager
        raise ValueError(f"Could not find '{name}' in {self.data['package_managers']}")

    def iter_specs_by_id(
        self,
        dep_url: str,
        package_manager: str,
        specs_type: TBuildHostRun | Iterable[TBuildHostRun] | None = None,
        **kwargs,
    ) -> Iterable[list[str]]:
        if "@" in dep_url and not dep_url.startswith("dep:virtual/"):
            # TODO: Virtual versions are not implemented
            # (e.g. how to map a language standard to a concrete version)
            dep_url, version = dep_url.split("@", 1)
        else:
            version = None
        if specs_type is None:
            specs_type = ("build", "host", "run")
        elif isinstance(specs_type, str):
            specs_type = (specs_type,)
        mgr = self.get_package_manager(package_manager)
        for entry in self.iter_by_id(dep_url, **kwargs):
            specs = list(dict.fromkeys(s for key in specs_type for s in entry["specs"][key]))
            if version:
                specs = [self._add_version_to_spec(spec, version, mgr) for spec in specs]
            yield specs

    def iter_install_commands(
        self,
        dep_url: str,
        package_manager: str,
        specs_type: TBuildHostRun | Iterable[TBuildHostRun] | None = None,
    ) -> Iterable[list[str]]:
        mgr = self.get_package_manager(package_manager)
        for specs in self.iter_specs_by_id(dep_url, package_manager, specs_type):
            yield self.build_install_command(mgr, specs)

    def build_install_command(
        self,
        package_manager: dict[str, Any],
        specs: list[str],
    ) -> list[str]:
        # TODO: Deal with `{}` placeholders
        cmd = []
        if package_manager.get("requires_elevation", False):
            # TODO: Add a system to infer type of elevation required (sudo vs Windows AUC)
            cmd.append("sudo")
        cmd.extend(package_manager["install_command"])
        cmd.extend(specs)
        return cmd

    def _add_version_to_spec(self, name: str, version: str, package_manager: dict) -> str:
        operator_mapping_config = package_manager.get("version_operators")
        if operator_mapping_config == {} or not version:
            return name

        final_operator_mapping = self.default_operator_mapping.copy()
        if operator_mapping_config:
            final_operator_mapping.update(operator_mapping_config)

        converted_versions = []
        for source_version_part in version.split(","):
            source_version_part = self._ensure_specifier_compatible(source_version_part)
            parsed = Specifier(source_version_part)
            source_operator = parsed.operator
            operator_key = Specifier._operators[source_operator]
            converted_operator = final_operator_mapping[operator_key]
            # Replace the original PEP440 operator with the target one
            if converted_operator is None:
                continue  # TODO: Warn? Error?
            converted = source_version_part.replace(source_operator, converted_operator)
            converted_versions.append(converted)

        if converted_versions:
            # Join the converted parts using the target 'and' string
            merged_versions = final_operator_mapping["and"].join(converted_versions)
            # Prepend the target separator
            return f"{name}{final_operator_mapping['separator']}{merged_versions}"

        # Return only name if no valid/convertible version parts were found
        return name

    def _ensure_specifier_compatible(self, value: str) -> Specifier:
        if not set(value).intersection("<>=!~"):
            return f"==={value}"
        return value


@cache
def default_ecosystems() -> Ecosystems:
    return Ecosystems.from_default()


@cache
def remote_mapping(ecosystem_or_url: str) -> Mapping:
    if ecosystem_or_url.startswith(("http://", "https://")):
        return Mapping.from_url(ecosystem_or_url)
    return Mapping.from_default(ecosystem_or_url)
