# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

"""
Parse dep: dependencies
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import unquote

from packageurl import PackageURL

if TYPE_CHECKING:
    from typing import AnyStr, ClassVar

    try:
        from typing import Self
    except ImportError:
        from typing_extensions import Self


class DepURL(PackageURL):
    SCHEME: ClassVar[str] = "dep"

    def __new__(
        cls,
        type: AnyStr | None = None,
        namespace: AnyStr | None = None,
        name: AnyStr | None = None,
        version: AnyStr | None = None,
        qualifiers: AnyStr | dict[str, str] | None = None,
        subpath: AnyStr | None = None,
    ) -> Self:
        # Validate virtual types _before_ the namedtuple is created
        if type.lower() == "virtual":
            namespace = namespace.lower()
            if namespace not in ("compiler", "interface"):
                raise ValueError(
                    "'dep:virtual/*' only accepts 'compiler' or 'interface' as namespace."
                )
            # names are normalized to lowercase
            name = name.lower()

        return super().__new__(
            cls,
            type=type,
            namespace=namespace,
            name=name,
            version=version,
            qualifiers=qualifiers,
            subpath=subpath,
        )

    def to_string(self) -> str:
        # Parent class forces quoting on qualifiers and some others, we don't want that.
        return unquote(super().to_string())

    def _version_as_vers(self) -> str:
        if set(self.version).intersection("<>=!~*"):
            # Version range
            vers_type = "pypi" if self.type in ("generic", "virtual", "pypi") else self.type
            return f"vers:{vers_type}/{self.version}"
        # Literal version
        return self.version or ""

    def to_purl_string(self) -> str:
        if self.type == "virtual":
            raise NotImplementedError
        components = self._asdict()
        maybe_vers = self._version_as_vers()
        if self.version and self.version != maybe_vers:
            components.pop("version", None)
            components["qualifiers"]["vers"] = maybe_vers
        return PackageURL(**components).to_string()

    def to_core_metadata_string(self) -> str:
        result = f"{'dep' if self.type == 'virtual' else 'pkg'}:{self.type}"
        if self.namespace:
            result += f"/{self.namespace}"
        result += f"/{self.name}"
        if self.version:
            result += f" ({self._version_as_vers()})"
        return result
