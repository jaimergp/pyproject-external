# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

"""
Parse dep: dependencies
"""

from packageurl import PackageURL, normalize


class DepURL(PackageURL):
    # TODO: Needs https://github.com/package-url/packageurl-python/pull/184
    SCHEME = "dep"

    def to_string(self) -> str:
        """
        Return a dep string built from components.
        """
        type, namespace, name, version, qualifiers, subpath = normalize(  # NOQA
            self.type,
            self.namespace,
            self.name,
            self.version,
            self.qualifiers,
            self.subpath,
            encode=False,
        )

        purl = [f"{self.SCHEME}:", type, "/"]

        if namespace:
            purl.append(namespace)
            purl.append("/")

        purl.append(name)

        if version:
            purl.append("@")
            purl.append(version)

        if qualifiers:
            purl.append("?")
            purl.append(qualifiers)

        if subpath:
            purl.append("#")
            purl.append(subpath)

        return "".join(purl)

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
