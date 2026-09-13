from csorchestrator.application.recipes.manifest_github import (
    install_ubuntu_apt_packages,
)
from csorchestrator.domain.orchestrator.orchestrator import Orchestrator


def install_requirements(
    orchestrator: Orchestrator,
    lib_list: list[str] | None = None,  # none means all
) -> None:
    if lib_list is None or "csBaseLibs" in lib_list:
        install_ubuntu_apt_packages(
            orchestrator,
            [
                "libgl1-mesa-dev",
                "libopengl-dev",
                "mesa-common-dev",
            ],
        )
