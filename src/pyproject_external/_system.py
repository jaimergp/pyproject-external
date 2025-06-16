# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
import logging
import platform
import shutil

import distro

from ._registry import default_ecosystems, remote_mapping

log = logging.getLogger(__name__)


def find_ecosystem_for_package_manager(package_manager: str) -> str:
    for ecosystem, mapping in default_ecosystems().iter_items():
        mapping = remote_mapping(mapping["mapping"])
        try:
            mapping.get_package_manager(package_manager)
        except ValueError:
            continue
        else:
            return ecosystem
    raise ValueError(f"No ecosystem found for package manager '{package_manager}'")


def detect_ecosystem_and_package_manager() -> tuple[str, str]:
    platform_system = platform.system()
    if platform_system == "Linux":
        distro_id = distro.id()
        for name in (distro_id, *distro.like().split()):
            mapping = default_ecosystems().get_mapping(name, default=None)
            if mapping:
                return name, mapping.package_managers[0]["name"]

        raise ValueError(f"No support for platform '{distro_id}' yet!")
    if platform_system == "Darwin":
        return "homebrew", "brew"
    if platform_system == "Windows" or platform_system.lower().startswith(("cygwin", "msys")):
        return "vcpkg", "vcpkg"  # TODO: Determine which one has the most complete mapping
    # Fallback to the conda ecosystem if available
    for name in ("conda", "pixi", "mamba", "micromamba"):
        if shutil.which(name):
            return "conda", name
    raise ValueError(f"No support for platform '{distro_id}' yet!")
