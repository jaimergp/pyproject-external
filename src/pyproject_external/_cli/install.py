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
from .._constants import PythonInstallers, UnsupportedConstraintsBehaviour
from .._exceptions import UnsupportedSpecError
from ._utils import NotOnCIError, _pyproject_text

log = logging.getLogger(__name__)
app = typer.Typer()
user_config = Config.load_user_config()


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
    ] = user_config.preferred_package_manager or "",
    installer: Annotated[
        PythonInstallers,
        typer.Option(help="Which tool should be used to install the package"),
    ] = PythonInstallers.PIP,
    python: Annotated[
        str,
        typer.Option(help="Python executable to use"),
    ] = sys.executable,
    unsupported_constraints_behaviour: Annotated[
        UnsupportedConstraintsBehaviour,
        typer.Option(
            help="Whether to error, warn or ignore unsupported version constraints when mapping. "
            "Constraints will be dropped if needed."
        ),
    ] = user_config.unsupported_constraints_behaviour,
    unknown_args: typer.Context = typer.Option(None),
) -> None:
    if not os.environ.get("CI"):
        raise NotOnCIError()

    package = Path(package)
    pyproject_text = _pyproject_text(package)
    pyproject = tomllib.loads(pyproject_text)
    external: External = External.from_pyproject_data(pyproject)
    external.validate(raises=False)

    if package_manager:
        ecosystem = find_ecosystem_for_package_manager(package_manager)
    else:
        ecosystem, package_manager = detect_ecosystem_and_package_manager()
    log.info("Detected ecosystem '%s' for package manager '%s'", ecosystem, package_manager)

    try:
        install_external_cmds = external.install_commands(
            ecosystem,
            package_manager=package_manager,
            with_version=True,
        )
    except UnsupportedSpecError as exc:
        if unsupported_constraints_behaviour == UnsupportedConstraintsBehaviour.ERROR:
            raise
        if unsupported_constraints_behaviour == UnsupportedConstraintsBehaviour.WARN:
            log.warning("UnsupportedSpecError: %s. Dropping version info.", exc)
        install_external_cmds = external.install_commands(
            ecosystem,
            package_manager=package_manager,
            with_version=False,
        )
    if installer == PythonInstallers.PIP:
        install_cmd = [python, "-m", "pip", "install"]
    elif installer == PythonInstallers.UV:
        install_cmd = ["uv", "pip", "install", "--python", python]
    else:
        raise ValueError(f"Unrecognized 'installer': {installer}")

    try:
        # 1. Install external dependencies
        for install_external_cmd in install_external_cmds:
            subprocess.run(install_external_cmd.render(), check=True)
        # 2. Build wheel
        with (
            activated_conda_env(package_manager=package_manager)
            if ecosystem == "conda-forge"
            else nullcontext(os.environ) as env
        ):
            subprocess.run([*install_cmd, *unknown_args.args, package], check=True, env=env)
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)  # avoid unnecessary typer pretty traceback
