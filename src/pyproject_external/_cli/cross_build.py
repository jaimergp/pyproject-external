# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025 Quansight Labs
"""
A specialized build command for cross-compiled wheels.

Only supports conda-forge for now.

Strategy:

- Create a build environment with Python, cross-python_{target-platform}, build_requires,
  and external.build_requirements. Patch mapping so the compilers are cross-compilers instead of native.
- Create a host environment with Python, build_requires, and external.build_host_requirements.
- Activate them in a stacked way so compiler activation can work.
- Run `python -m build --wheel --no-isolation --skip-dependency-check .` from host environment.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import traceback
from collections.abc import Mapping, Sequence
from functools import cache
from pathlib import Path
from platform import mac_ver
from tempfile import TemporaryDirectory
from typing import Annotated

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import typer
from build import ProjectBuilder
from packaging.requirements import Requirement
from packaging.tags import platform_tags

from .. import (
    Config,
    External,
    activated_conda_env,
)
from .._constants import UnsupportedConstraintsBehaviour
from ._utils import _handle_ecosystem_and_package_manager, _pyproject_text

log = logging.getLogger(__name__)
app = typer.Typer()
user_config = Config.load_user_config()


def conda_build_env(build_prefix: Path, host_prefix: Path, platform: str) -> dict[str, str]:
    env = os.environ.copy()
    # Need these conda-build env vars so compiler activation and cross-python do its magic
    env["CONDA_BUILD"] = "1"
    env["CONDA_BUILD_STATE"] = "BUILD"
    env["BUILD_PREFIX"] = str(build_prefix)
    env["PREFIX"] = str(host_prefix)
    env["PYTHON"] = str(host_prefix / "bin" / "python")
    env["build_platform"] = native_platform()
    env["target_platform"] = platform
    return env


def create_environment(packages: list[str], name: str, platform: str | None = None) -> Path:
    path = TemporaryDirectory(prefix=f"cross-env-{name}-", delete=False)
    command = [
        "micromamba",
        "create",
        "--prefix",
        path.name,
        "--override-channels",
        "--channel=conda-forge",
        "--yes",
        # "--quiet",
    ]
    if platform:
        command.extend(["--platform", platform])
    command.extend(packages)
    subprocess.run(command, check=True)
    atexit.register(shutil.rmtree, path.name)
    return Path(path.name)


@cache
def native_platform() -> str:
    out = subprocess.check_output(["micromamba", "info", "--json"])
    return json.loads(out)["platform"]


def get_platform_tags(platform: str) -> list[str]:
    if sys.platform.startswith("linux"):
        if platform == "linux-64":
            os.environ["_PYTHON_HOST_PLATFORM"] = "linux-x86_64"
        else:
            os.environ["_PYTHON_HOST_PLATFORM"] = platform
    elif sys.platform == "darwin":
        osx_ver, _, _ = mac_ver()
        arch = "x86_64" if platform == "osx-64" else "arm64"
        os.environ["_PYTHON_HOST_PLATFORM"] = f"macosx-{osx_ver[0]}.{osx_ver[1]}-{arch}"
    tags = list(platform_tags())
    del os.environ["_PYTHON_HOST_PLATFORM"]
    return tags


def maybe_replace_compiler(package: str, platform: str) -> list[str]:
    native_os = sys.platform
    if native_os.startswith("linux"):
        if package == "c-compiler":
            return ["gcc", f"gcc_{platform}=14"]
        if package == "cxx-compiler":
            return ["gxx", f"gxx_{platform}=14", "gcc", f"gcc_{platform}=14"]
        if package == "fortran-compiler":
            return ["gfortran", f"gfortran_{platform}", f"gcc_{platform}", "binutils"]
        if package == "rust":
            return [f"rust_{platform}"]
        return [package]
    if native_os == "darwin":
        if package == "c-compiler":
            return ["cctools>=949.0.1", "ld64>=530", "llvm-openmp", f"clang_{platform}=19"]
        if package == "cxx-compiler":
            return [
                "cctools>=949.0.1",
                "ld64>=530",
                "llvm-openmp",
                f"clang_{platform}=19",
                f"clangxx_{platform}=19",
            ]
        if package == "fortran-compiler":
            return [
                "cctools>=949.0.1",
                "ld64>=530",
                "llvm-openmp",
                "gfortran",
                f"gfortran_{platform}=14",
            ]
        if package == "rust":
            return [f"rust_{platform}"]
        return [package]
    if native_os == "win32":
        if package == "c-compiler":
            return [f"vs2022_{platform}"]
        if package == "cxx-compiler":
            return [f"vs2022_{platform}"]
        if package == "fortran-compiler":
            return [f"flang_{platform}=19"]
        if package == "rust":
            return [f"rust_{platform}"]
        return [package]
    raise ValueError(f"Native platform not supported: {native_os}")


def sysroots(platform: str, version: str) -> list[str]:
    if platform.startswith("linux-"):
        return [f"sysroot_{native_platform()}=2.17", f"sysroot_{platform}=2.17"]
    if platform.startswith("osx-"):
        return [f"sdkroot_env_{platform}=11.0"]
    raise ValueError(f"Unrecognized platform: {platform}")


@app.command(
    help=__doc__,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def cross_build(
    package: Annotated[
        str,
        typer.Argument(
            help="Package to build wheel for."
            "It can be a path to a pyproject.toml-containing directory, "
            "or a source distribution."
        ),
    ],
    platform: Annotated[
        str,
        typer.Option(
            help="Target platform to cross-compile for, in conda subdir syntax; "
            "e.g. linux-aarch64 or osx-arm64."
        ),
    ],
    ecosystem: Annotated[
        str,
        typer.Option(
            help="Install external dependencies from this ecosystem, instead of the "
            "auto-detected one."
        ),
    ] = user_config.preferred_ecosystem or "conda-forge",
    package_manager: Annotated[
        str,
        typer.Option(
            help="Use this package manager to install the external dependencies "
            "instead of the auto-detected one."
        ),
    ] = user_config.preferred_package_manager or "micromamba",
    outdir: Annotated[
        str | None,
        typer.Option(help="Output directory for the wheel. Defaults to working directory"),
    ] = None,
    python_version: Annotated[
        str,
        typer.Option(help="Python version to compile for"),
    ] = ".".join(map(str, sys.version_info[:2])),
    unsupported_constraints_behaviour: Annotated[
        UnsupportedConstraintsBehaviour,
        typer.Option(
            help="Whether to error, warn or ignore unsupported version constraints. "
            "Constraints will be dropped if needed."
        ),
    ] = user_config.unsupported_constraints_behaviour,
    env_vars: Annotated[
        str,
        typer.Option(
            help="JSON dictionary as a string with additional environment variables to pass to "
            "the wheel building process. Templates '{prefix}' and '{build_prefix}' are supported "
            "for the paths to the host and build environments, respectively."
        ),
    ] = "",
    unknown_args: typer.Context = typer.Option(()),
) -> None:
    package = Path(package)
    pyproject_text = _pyproject_text(package)
    pyproject = tomllib.loads(pyproject_text)
    external: External = External.from_pyproject_data(pyproject)
    external.validate(raises=False)
    ecosystem, package_manager = _handle_ecosystem_and_package_manager(ecosystem, package_manager)

    if ecosystem != "conda-forge":
        raise ValueError("Only --ecosystem=conda-forge supported for now")
    if package_manager != "micromamba":
        raise ValueError("Only --package-manager=micromamba supported for now")

    # Get Python dependencies from pyproject.toml
    with TemporaryDirectory(delete=False) as tmp:
        atexit.register(shutil.rmtree, tmp)
        with tarfile.open(package) as tar:
            tar.extractall(tmp)
        project_dir = next(Path(tmp).glob("*/"))
        builder = ProjectBuilder(project_dir)

    # 1. Create build environment with build deps and cross Python
    # Compiler needs to be a cross-compiler!
    build_deps = []
    for dep in external.map_versioned_dependencies(
        "conda-forge",
        categories=["build_requires"],
        package_manager="micromamba",
    ):
        build_deps.extend(maybe_replace_compiler(dep, platform))

    build_deps.extend(
        [
            f"cross-python_{platform}",
            f"python={python_version}",
            "pip",
            *sysroots(platform, "unused for now"),
        ]
    )

    build_env = create_environment(build_deps, name="build")
    subprocess.run(
        [
            build_env / "bin" / "python",
            "-m",
            "pip",
            "install",
            "build",
            # This list is static in TOML and can be passed as is
            *builder.build_system_requires,
        ],
        check=True,
    )

    # 2a. Create host environment with host deps
    host_deps = external.map_versioned_dependencies(
        "conda-forge",
        categories=["build_host_requires"],
        package_manager="micromamba",
    )
    host_deps.append(f"python={python_version}")
    host_env = create_environment(host_deps, name="host", platform=platform)

    # Now we need to add some more dependencies to build and host.
    # Build backends may specify their own dependencies in a dynamic way
    # e.g. frozenlist ships its own in-tree build backend. This needs
    # to be checked with the build env's Python so it can import the installed modules.
    with activated_conda_env(
        "micromamba",
        build_env,
        initial_env=conda_build_env(build_env, host_env, platform),
    ) as build_env_vars:

        def _activated_runner(
            cmd: Sequence[str],
            cwd: str | None = None,
            extra_environ: Mapping[str, str] | None = None,
        ) -> None:
            env = build_env_vars.copy()
            if extra_environ:
                env.update(extra_environ)

            subprocess.check_call(cmd, cwd=cwd, env=env)

        try:
            if extra_build_deps := ProjectBuilder(
                project_dir,
                python_executable=build_env / "bin" / "python",
                runner=_activated_runner,
            ).get_requires_for_build("wheel"):
                subprocess.run(
                    [
                        build_env / "bin" / "python",
                        "-m",
                        "pip",
                        "install",
                        *extra_build_deps,
                    ],
                    check=True,
                )
        except Exception as exc:
            print(
                "! ERROR: Could not detect additional build backend requirements.",
                "Build will continue but may fail later!",
                file=sys.stderr,
            )
            traceback.print_exception(exc, file=sys.stderr)

    # 2b. Install Python build requirements for host too. We can only use the build env Python
    # so we need to configure it for the host environment with the adequate platform tags.
    subprocess.run(
        [
            str(build_env / "bin" / "python"),
            "-m",
            "pip",
            "install",
            *[f"--platform={p}" for p in get_platform_tags(platform)],
            "--only-binary=:all:",
            f"--target={host_env}",
            "build",
            *builder.build_system_requires,
            *extra_build_deps,
        ],
        check=True,
    )

    with (
        activated_conda_env(
            "micromamba",
            host_env,
            python=str(build_env / "bin/python"),
            initial_env=conda_build_env(build_env, host_env, platform),
        ) as host_env_vars,
        activated_conda_env(
            "micromamba",
            build_env,
            initial_env=host_env_vars,
            stack=True,
        ) as build_env_vars,
    ):
        # Inject custom environment variables that may be needed for the build process
        if (
            pyproject_env_vars := pyproject.get("tool", {})
            .get("pyproject-external", {})
            .get("cross-build-env-vars")
        ):
            for key, value in pyproject_env_vars.items():
                build_env_vars[key] = value.format(prefix=host_env, build_prefix=build_env)
        if env_vars:
            if isinstance(env_vars, str):
                env_vars = json.loads(env_vars)
            for key, value in (env_vars or {}).items():
                build_env_vars[key] = value.format(prefix=host_env, build_prefix=build_env)

        # 3. Run `python -m build`
        cmd = [
            host_env / "bin" / "python",
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--skip-dependency-check",
        ]
        if "meson-python" in (Requirement(req).name for req in builder.build_system_requires) and (
            meson_args := build_env_vars.get("MESON_ARGS")
        ):
            meson_args = meson_args.replace("--buildtype release ", "")
            meson_args += f" --pkg-config-path={host_env}/lib/pkgconfig"
            meson_args = [f"-Csetup-args={arg}" for arg in meson_args.split()]
            cmd.extend(meson_args)
            # HACK from https://github.com/conda-forge/scipy-feedstock/blob/511c9db6ae4/recipe/build.sh#L6C1-L10C79
            if (meson_cross_file := (build_env / "meson_cross_file.txt")).exists():
                original_cross_file = meson_cross_file.read_text()
                meson_cross_file.write_text(
                    f"{original_cross_file}\npython = '{host_env}/bin/python'"
                )
        cmd.append(project_dir)
        subprocess.run(
            cmd,
            check=True,
            env=build_env_vars,
        )
