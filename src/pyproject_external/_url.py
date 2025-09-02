# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

"""
Parse DepURLs (`dep:` strings)
"""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING
from urllib.parse import unquote

from packageurl import PackageURL
from packaging.markers import InvalidMarker, Marker

if TYPE_CHECKING:
    from typing import AnyStr, ClassVar

    try:
        from typing import Self
    except ImportError:
        from typing_extensions import Self

log = getLogger(__name__)


class DepURL(PackageURL):
    """
    A PURL derivative with some changes to accommodate PEP 725 requirements.

    Main differences:

    - The scheme is `dep:`, not `pkg:`.
    - The version field (`@...`) allows version ranges.
    - A new *type*, `virtual`, is recognized, with two namespaces: `compiler` and `interface`.
    """

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
            if not namespace or namespace.lower() not in ("compiler", "interface"):
                raise ValueError(
                    "'dep:virtual/*' only accepts 'compiler' or 'interface' as namespace."
                )
            namespace = namespace.lower()
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

    @classmethod
    def from_string(cls, value: str) -> Self:
        """
        Generate a DepURL object from a string, optionally containing an environment marker.

        If present, the environment marker will be moved to an `environment_marker` qualifier.
        """
        if ";" in value:
            depurl, marker = value.rsplit(";", 1)
            try:
                Marker(marker)  # just check if it's parsable, we store it as string
            except InvalidMarker:
                log.warning(
                    "Invalid marker detected %s. Parsing whole string as a DepURL.", marker
                )
                depurl = value
                marker = None
        else:
            depurl = value
            marker = None
        parsed = super().from_string(depurl)
        if marker is not None:
            parsed.qualifiers["environment_marker"] = marker
        return parsed

    def to_string(self, drop_environment_marker: bool = True) -> str:
        """
        Generate a string, with no %-encoding.
        """
        components = self._asdict()
        # We don't want to export the environment marker
        components["qualifiers"] = components.get("qualifiers", {}).copy()
        components.get("qualifiers", {}).pop("environment_marker", None)
        # Parent class forces quoting on qualifiers and some others, we don't want that.
        as_string = f"dep:{unquote(PackageURL(**components).to_string())[4:]}"
        if not drop_environment_marker and self.environment_marker:
            return f"{as_string}; {self.environment_marker}"
        return as_string

    def _version_as_vers(self) -> str:
        if set(self.version).intersection("<>=!~*"):
            # Version range
            vers_type = "pypi" if self.type in ("generic", "virtual", "pypi") else self.type
            return f"vers:{vers_type}/{self.version}"
        # Literal version
        return self.version or ""

    def to_purl_string(self) -> str:
        """
        Generate a PURL string, with `pkg:` as the scheme, moving the version
        information to a `?vers` qualifier and raising if `dep:virtual/*` cases are passed.
        """
        if self.type == "virtual":
            raise NotImplementedError
        components = self._asdict()
        maybe_vers = self._version_as_vers()
        if self.version and self.version != maybe_vers:
            components.pop("version", None)
            components["qualifiers"]["vers"] = maybe_vers
        return PackageURL(**components).to_string()

    def to_core_metadata_string(self) -> str:
        """
        Generate a Core Metadata v2.5 string for DepURLs.

        TODO: Remove?
        """
        result = f"{'dep' if self.type == 'virtual' else 'pkg'}:{self.type}"
        if self.namespace:
            result += f"/{self.namespace}"
        result += f"/{self.name}"
        if self.version:
            result += f" ({self._version_as_vers()})"
        return result

    def evaluate_environment_marker(self) -> bool:
        if (marker := self.environment_marker) is not None:
            return marker.evaluate()
        return True

    @property
    def environment_marker(self) -> Marker | None:
        if marker := self.qualifiers.get("environment_marker"):
            return Marker(marker)
        return None
