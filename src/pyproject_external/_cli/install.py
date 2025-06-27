# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
"""
Install a project (building the wheel if necessary) in the desired location.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import Annotated

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import typer

# Only import from __init__ to make sure the only uses the public interface
from .. import (
    Config,
    External,
    activated_conda_env,
    detect_ecosystem_and_package_manager,
    find_ecosystem_for_package_manager,
)
from ._utils import _pyproject_text

help = __doc__

log = logging.getLogger(__name__)


def main(
    package: Annotated[
        str,
        typer.Argument(
            help="Package to build wheel for and then install. "
            "It can be a path to a pyproject.toml-containing directory, "
            "or a source distribution."
        ),
    ],
    package_manager: Annotated[
        str,
        typer.Option(
            help="If given, use this package manager to install the external dependencies "
            "rather than the auto-detected one."
        ),
    ] = Config.load_user_config().preferred_package_manager or "",
) -> None:
    if not os.environ.get("CI"):
        raise RuntimeError("This tool can only be used in CI environments. Set CI=1 to override.")

    package = Path(package)
    pyproject_text = _pyproject_text(package)
    pyproject = tomllib.loads(pyproject_text)
    external = External.from_pyproject_data(pyproject)
    external.validate()

    if package_manager:
        ecosystem = find_ecosystem_for_package_manager(package_manager)
    else:
        ecosystem, package_manager = detect_ecosystem_and_package_manager()
    log.info("Detected ecosystem '%s' for package manager '%s'", ecosystem, package_manager)
    install_external_cmd = external.install_command(ecosystem, package_manager=package_manager)
    install_pip_cmd = [sys.executable, "-m", "pip", "install", package]
    try:
        # 1. Install external dependencies
        subprocess.run(install_external_cmd, check=True)
        with (
            activated_conda_env(package_manager=package_manager)
            if ecosystem == "conda-forge"
            else nullcontext(os.environ) as env
        ):
            # 2. Build wheel and install with pip
            subprocess.run(install_pip_cmd, check=True, env=env)
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)  # avoid unnecessary typer pretty traceback
