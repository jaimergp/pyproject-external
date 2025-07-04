# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
"""
CLI to work with PEP 725 external metadata.
"""

import typer

from .build import help as _build_help
from .build import main as _build
from .install import help as _install_help
from .install import main as _install
from .show import help as _show_help
from .show import main as _show

app = typer.Typer(
    help=__doc__,
    no_args_is_help=True,
    add_completion=False,
)


show = app.command("show", no_args_is_help=True, help=_show_help)(_show)
build = app.command("build", no_args_is_help=True, help=_build_help)(_build)
install = app.command("install", no_args_is_help=True, help=_install_help)(_install)


if __name__ == "__main__":
    app()
