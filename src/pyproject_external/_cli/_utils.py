import logging
import tarfile
from pathlib import Path

import typer

from .._registry import Mapping
from .._system import (
    detect_ecosystem_and_package_manager,
    find_ecosystem_for_package_manager,
    first_package_manager_in_mapping,
)

log = logging.getLogger(__name__)


def _read_pyproject_from_sdist(path: Path) -> str:
    with tarfile.open(path) as tar:
        for info in tar.getmembers():
            name = info.name
            if "/" in name and name.split("/")[-1] == "pyproject.toml":
                return tar.extractfile(info).read().decode()
    raise ValueError("Could not read pyproject.toml file from sdist")


def _pyproject_text(package: Path) -> str:
    if package.is_file():
        if not package.name.lower().endswith(".tar.gz"):
            raise typer.BadParameter(f"Given package '{package}' is a file, but not a sdist.")
        return _read_pyproject_from_sdist(package)
    if package.is_dir():
        return (package / "pyproject.toml").read_text()
    raise typer.BadParameter(f"Package {package} is not a valid path.")


def _handle_ecosystem_discovery(
    ecosystem: str,
    package_manager: str,
    prepend: str = "",
    append: str = "",
) -> tuple[str, str]:
    if ecosystem and package_manager:
        pass
    elif ecosystem:
        package_manager = first_package_manager_in_mapping(ecosystem)
    elif package_manager:
        ecosystem = find_ecosystem_for_package_manager(package_manager)
    else:
        ecosystem, package_manager = detect_ecosystem_and_package_manager()
    log.info("Using ecosystem '%s' and package manager '%s'", ecosystem, package_manager)
    if prepend or append:
        ecosystem = Mapping.from_any(ecosystem)
        if prepend:
            log.debug("Prepended '%s'", prepend)
            ecosystem = Mapping.merge(Mapping.from_any(prepend), ecosystem)
        if append:
            log.debug("Appended '%s'", append)
            ecosystem = Mapping.merge(ecosystem, Mapping.from_any(append))
    return ecosystem, package_manager


class NotOnCIError(RuntimeError):
    def __init__(self):
        super().__init__(
            "This tool should only be used in CI or ephemeral environments!\n\n"
            "It will likely install system packages as a side effect of providing the "
            "external dependencies required to build the wheels.\n\n"
            "If you understand the risks, set CI=1 to override."
        )
