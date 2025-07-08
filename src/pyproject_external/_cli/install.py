# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
"""
Install a project in the given location. Wheels will be built as needed.
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

from .. import (
    Config,
    External,
    activated_conda_env,
    detect_ecosystem_and_package_manager,
    find_ecosystem_for_package_manager,
)
from ._utils import NotOnCIError, _Installers, _pyproject_text

log = logging.getLogger(__name__)
app = typer.Typer()


@app.command(
    help=__doc__,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def install(
    package: Annotated[
        str,
        typer.Argument(
            help="Package to build wheel for."
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
    installer: Annotated[
        _Installers,
        typer.Option(help="Which tool should be used to install the package"),
    ] = _Installers.pip,
    unknown_args: typer.Context = typer.Option(()),
) -> None:
    if not os.environ.get("CI"):
        raise NotOnCIError()

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
    if installer == _Installers.pip:
        install_cmd = [sys.executable, "-m", "pip", "install"]
    elif installer == _Installers.uv:
        install_cmd = ["uv", "pip", "install", "--python", sys.executable]
    else:
        raise ValueError(f"Unrecognized 'installer': {installer}")

    try:
        # 1. Install external dependencies
        subprocess.run(install_external_cmd, check=True)
        # 2. Build wheel
        with (
            activated_conda_env(package_manager=package_manager)
            if ecosystem == "conda-forge"
            else nullcontext(os.environ) as env
        ):
            subprocess.run([*install_cmd, *unknown_args.args, package], check=True, env=env)
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)  # avoid unnecessary typer pretty traceback
