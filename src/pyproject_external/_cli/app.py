# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
"""
CLI to work with PEP 725 / 804 external metadata.
"""

import logging

import typer
from rich.console import Console
from rich.logging import RichHandler

from .build import app as _install
from .install import app as _build
from .prepare import app as _prepare
from .query import app as _query
from .show import app as _show

app = typer.Typer(
    help=__doc__,
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(_show)
app.add_typer(_query)
app.add_typer(_install)
app.add_typer(_prepare)
app.add_typer(_build)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=Console(stderr=True))],
)

if __name__ == "__main__":
    app()
