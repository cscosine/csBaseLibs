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
from csorchestrator.application.recipes.manifest_github import (
    download_csorchestrator_managed_libraries,
)
from csorchestrator.foundation.core.report import Report
from csorchestrator.frontend.cscmake_presets.supported_variants import BuildConfig
from csorchestrator.frontend.step.step_get_precompiled_lib_github import StepGetPrecompiledLibGithub

from csBaseLibs.cs_orchestrator_config import install_requirements
from libs.csQt6.cs_orchestrator_config import qt6_mapping


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
        name="csBaseLibs",
        version="0.1.0",
        base_install_dir=base_install_dir,
        additional_files_list=[Path("csBaseLibs/cs_orchestrator_config.py")],
    )

    # ----------------------------------------------------------------
    checkout_repos(
        orchestrator=o,
        base_target_dir=base_target_dir,
        repo_ref_build_type_list=repos,
        repo_access_token="${{ secrets.ACTIONS_ORG_ACCESS }}",
    )

    # ----------------------------------------------------------------
    install_requirements(o)

    # ----------------------------------------------------------------
    # Get Precompiled Libraries
    #

    report.append_report(
        download_csorchestrator_managed_libraries(
            orchestrator=o,
            base_url=StepGetPrecompiledLibGithub.GITHUB_BASE_URL_HTTPS,
            org="cscosine",
            git_repo="3rdPartyBaseLibs",
            project_name="3rdPartyBaseLibs",
            project_version="0.1.0",
            release_tag="vX.X.X",
            base_libs_dir=base_libs_dir,
        )
    )

    report.append_report(
        download_csorchestrator_managed_libraries(
            orchestrator=o,
            base_url=StepGetPrecompiledLibGithub.GITHUB_BASE_URL_HTTPS,
            org="cscosine",
            git_repo="csQt6",
            project_name="Qt6",
            project_version="v6.11.1",
            release_tag="vX.X.X",
            base_libs_dir=base_libs_dir,
            mapping_function=qt6_mapping,
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
        return OptionalOrchestratorWithReport.createReport(report)
    return OptionalOrchestratorWithReport.createResultAndReport(o, report)


def main(argv: Sequence[str] | None = None) -> int:
    script_path = str(Path(__file__).resolve())
    return orchestrator_main_with_default_run(script_path, argv)


if __name__ == "__main__":
    sys.exit(main())
