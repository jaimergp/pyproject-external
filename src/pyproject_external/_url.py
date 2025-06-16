# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

"""
Parse dep: dependencies
"""
from urllib.parse import unquote

from packageurl import PackageURL


class DepURL(PackageURL):
    SCHEME = "dep"

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
