#!/usr/bin/env python3
import sys
from collections.abc import Sequence
from pathlib import Path

from csorchestrator.application.cli.cli import orchestrator_main_with_default_run
from csorchestrator.application.factory.factory import OptionalOrchestratorWithReport
from csorchestrator.application.recipes.checkout_build import (
    build_repos,
    checkout_repos,
    create_and_upload_artifacts,
)
from csorchestrator.application.recipes.create_orchestrator import create_default_orchestrator
from csorchestrator.foundation.core.report import Report
from csorchestrator.frontend.cscmake_presets.supported_variants import BuildConfig

from csfoundation.csorchestrator_config import (
    CSFOUNDATION_PROJECT_NAME,
    CSFOUNDATION_PROJECT_VERSION,
    install_csfoundation_build_dependencies,
)


def create_orchestrator() -> OptionalOrchestratorWithReport:
    report = Report()

    base_target_dir = Path("workspace")
    base_install_dir = base_target_dir / Path("install")
    base_libs_dir = base_target_dir / Path("libs")
    common_repo_ref = "dev"

    repos: dict[str, tuple[str, BuildConfig | None]] = {
        "csCMake": (common_repo_ref, None),
        "csCore": (common_repo_ref, BuildConfig.DEBUG_RELEASE_RELWITHDEBINFO_PARANOID),
        "csLie": (common_repo_ref, BuildConfig.DEBUG_RELEASE_RELWITHDEBINFO_PARANOID),
        "csCamera": (common_repo_ref, BuildConfig.DEBUG_RELEASE_RELWITHDEBINFO_PARANOID),
        "csVisOpenGL": (common_repo_ref, BuildConfig.DEBUG_RELEASE_RELWITHDEBINFO_PARANOID),
    }

    o = create_default_orchestrator(
        name=CSFOUNDATION_PROJECT_NAME,
        version=CSFOUNDATION_PROJECT_VERSION,
        base_install_dir=base_install_dir,
        additional_files_list=[Path("csfoundation/csorchestrator_config.py")],
    )

    # ----------------------------------------------------------------
    checkout_repos(
        orchestrator=o,
        base_target_dir=base_target_dir,
        repo_ref_build_type_list=repos,
        repo_access_token="${{ secrets.ACTIONS_ORG_ACCESS }}",
    )

    # ----------------------------------------------------------------
    # Install Requirements (Linux-Ubuntu) & Get Precompiled Libraries
    #
    # The auto-install helper installs the Linux system requirements for the
    # libraries being built and downloads, transitively and cross-repo, only
    # the managed libraries they need from the third_party_base_libs and
    # csqt6 releases (e.g. qt6 only when csVisOpenGL is built).
    built_first_party_libs = [repo for repo, (_, config) in repos.items() if config is not None]

    report.append_report(
        install_csfoundation_build_dependencies(
            orchestrator=o,
            base_libs_dir=base_libs_dir,
            required_libs=built_first_party_libs,
        )
    )

    # ----------------------------------------------------------------
    build_repos(
        orchestrator=o,
        base_target_dir=base_target_dir,
        repo_ref_build_type_list=repos,
    )

    create_and_upload_artifacts(
        orchestrator=o,
        base_install_dir=base_install_dir,
        repo_ref_build_type_list=repos,
    )

    # single return point
    if report.has_errors():
        return OptionalOrchestratorWithReport.create_report(report)
    return OptionalOrchestratorWithReport.create_result_and_report(o, report)


def main(argv: Sequence[str] | None = None) -> int:
    script_path = str(Path(__file__).resolve())
    return orchestrator_main_with_default_run(script_path, argv)


if __name__ == "__main__":
    sys.exit(main())
