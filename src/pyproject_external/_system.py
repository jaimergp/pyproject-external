# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
import logging
import os
import platform
import shutil
from pathlib import Path

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
    if os.environ.get("CONDA_PREFIX"):
        # An active conda environment is present; probably want to use that
        for tool in ("conda", "pixi", "mamba"):
            if exe := os.environ.get(f"{tool.upper()}_EXE"):
                exe = Path(exe)
                if exe.is_file():
                    if exe.stem == "micromamba":
                        return "conda-forge", "micromamba"
                    return "conda-forge", tool

    platform_system = platform.system()
    if platform_system == "Linux":
        distro_id = distro.id()
        for name in (distro_id, *distro.like().split()):
            mapping = default_ecosystems().get_mapping(name, default=None)
            if mapping:
                return name, mapping.package_managers[0]["name"]
        raise ValueError(f"No support for platform '{distro_id}' yet!")

    if platform_system == "Darwin":
        if shutil.which("brew"):
            return "homebrew", "brew"
        raise ValueError("Only homebrew is supported on macOS!")

    if platform_system == "Windows" or platform_system.lower().startswith(("cygwin", "msys")):
        return "vcpkg", "vcpkg"  # TODO: Determine which one has the most complete mapping

    # Fallback to the conda ecosystem if available, even if no active environments are found
    for name in ("conda", "pixi", "mamba", "micromamba"):
        if shutil.which(name):
            return "conda-forge", name

    raise ValueError(f"No support for platform '{distro_id}' yet!")
