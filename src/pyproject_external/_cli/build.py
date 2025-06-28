# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
"""
Build wheels while handling external metadata installation.
"""
import typer

app = typer.Typer()

@app.command(help=__doc__)
def build() -> None:
    print("Not implemented yet.")
