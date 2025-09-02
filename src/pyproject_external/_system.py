# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs

"""
Utilities to detect and interface with system properties.
"""

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

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


@contextmanager
def activated_conda_env(
    package_manager: str, prefix: str | None = None
) -> Iterable[dict[str, str]]:
    """
    Mimics environment activation by generating the activation 'hook' (the code
    that runs when a user types 'micromamba activate <prefix>') and a little Python
    reporter that writes the new and modified to a json file. This file is then
    read and applied to the test scope with 'monkeypatch'.
    """
    if not prefix:
        prefix = os.environ.get("CONDA_PREFIX", sys.prefix)
    if sys.platform == "win32":
        shell = "cmd.exe"
        script_ext = "bat"
        exe = ".exe"
        call = "CALL "
        args = ("/D", "/C")
    else:
        shell = "bash"
        script_ext = "sh"
        exe = call = ""
        args = ()
    if package_manager in ("micromamba", "mamba"):
        activate_cmd = [
            package_manager,
            "shell",
            "activate",
            "--prefix",
            prefix,
            "--shell",
            shell,
        ]
        deactivate_cmd = [
            package_manager,
            "shell",
            "deactivate",
            "--shell",
            shell,
        ]
    elif package_manager == "conda":
        activate_cmd = [
            "conda",
            f"shell.{shell}",
            "activate",
            prefix,
        ]
        deactivate_cmd = [
            "conda",
            f"shell.{shell}",
            "deactivate",
        ]
    elif package_manager == "pixi":
        activate_cmd = [
            "pixi",
            "shell-hook",
            "--shell",
            "cmd" if shell == "cmd.exe" else shell,
        ]
        deactivate_cmd = []
    environ = os.environ.copy()
    with TemporaryDirectory(prefix="pyproject-external-conda-activator-") as tmp_path:
        tmp_path = Path(tmp_path)
        hookfile = tmp_path / f"__hook.{script_ext}"
        # 'activate_cmd' prints the shell logic that would have run in the
        # real 'activate' command
        with _catch_activation_errors(True):
            hook = subprocess.check_output(activate_cmd, text=True, env=environ)
        outputfile = tmp_path / "__output.json"
        hookfile.write_text(
            f"{call}{hook}\n"
            # Report the changes in os.environ to a temporary file
            + f'{call}python{exe} -c "import json, os; print(json.dumps(dict(**os.environ)))" > "{outputfile}"'
        )
        with _catch_activation_errors(True):
            subprocess.run([shell, *args, hookfile], check=True, env=environ)
        # Recover and apply the os.environ changes to the running test; delete keys not present
        # in the activated environment, add/overwrite the ones that do appear.
        activated = json.loads(outputfile.read_text())

    for key in os.environ:
        if key not in activated:
            environ.pop(key)
    for key, value in activated.items():
        environ[key] = value

    yield environ

    # Deactivate directly in case there were filesystem changes
    if deactivate_cmd:
        with TemporaryDirectory(prefix="pyproject-external-conda-deactivator-") as tmp_path:
            tmp_path = Path(tmp_path)
            hookfile = tmp_path / f"__hook.{script_ext}"

            with _catch_activation_errors(False):
                hook = subprocess.check_output(deactivate_cmd, text=True, env=environ)

            hookfile.write_text(f"{call}{hook}\n")

            with _catch_activation_errors(False):
                subprocess.run([shell, *args, hookfile], check=False, env=environ)


@contextmanager
def _catch_activation_errors(activate: bool = True) -> Iterable[None]:
    try:
        yield
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Could not {'activate' if activate else 'deactivate'} conda environment!\n"
            f"Return code: {exc.returncode}\n"
            + (f"Stdout:\n{exc.stdout}\n" if exc.stdout else "")
            + (f"Stderr:\n{exc.stderr}\n" if exc.stderr else "")
        ) from exc
