import logging

import distro

from ._registry import default_ecosystems, remote_mapping

log = logging.getLogger(__name__)


def detect_ecosystem(package_manager: str) -> str:
    for ecosystem, mapping in default_ecosystems().iter_items():
        mapping = remote_mapping(mapping["mapping"])
        try:
            mapping.get_package_manager(package_manager)
        except ValueError:
            continue
        else:
            return ecosystem
    raise ValueError(f"No ecosystem detected for package manager '{package_manager}'")


def detect_ecosystem_and_package_manager() -> tuple[str, str]:
    for name in (distro.id(), distro.like()):
        if name == "darwin":
            return "homebrew", "brew"
        mapping = default_ecosystems().get_mapping(name, default=None)
        if mapping:
            return name, mapping.package_managers[0]["name"]

    log.warning("No support for distro %s yet", distro.id())
    # FIXME
    return "fedora", "dnf"
