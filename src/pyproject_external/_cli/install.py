# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
"""
Install a project in the given location. Wheels will be built as needed while.
"""

import typer

app = typer.Typer()


@app.command(help=__doc__)
def install() -> None:
    print("Not implemented yet.")
