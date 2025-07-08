import tarfile
from enum import Enum
from pathlib import Path

import typer


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


class _Installers(str, Enum):
    pip = "pip"
    uv = "uv"


class NotOnCIError(RuntimeError):
    def __init__(self):
        super().__init__(
            "This tool should only be used in CI or ephemeral environments!\n\n"
            "It will likely install system packages as a side effect of providing the "
            "external dependencies required to build the wheels.\n\n"
            "If you understand the risks, set CI=1 to override."
        )
