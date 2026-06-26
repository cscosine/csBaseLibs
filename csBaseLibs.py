#!/usr/bin/env python3
import sys
from pathlib import Path
from typing import Sequence

from csorchestrator.foundation.core.report import Report
from csorchestrator.foundation.core.optional_result_with_report import (
    OptionalResultWithReport,
)
from csorchestrator.foundation.git.resolve_url import RepoUrlParts

from csorchestrator.domain.orchestrator.workflow_config import (
    WorkflowConfig,
    Cron,
    DayOfWeek,
    ReleaseCreationOnTagConfig,
)
from csorchestrator.domain.context.context_os_architecture import OS
from csorchestrator.domain.context.context_os_architecture import UBUNTU_STRING_PREFIX

from csorchestrator.frontend.cscmake_presets.supported_variants import (
    BuildConfig,
)

from csorchestrator.frontend.step.step_get_repository import (
    StepGetRepositoryGitHub,
    StepGetRepositoryExtraDepthOne,
    StepGetRepositoryExtraAccessToken,
)
from csorchestrator.frontend.step.step_cmake_command import StepCMakeWorkflow
from csorchestrator.frontend.step.step_get_versions_from_cmake_config_package_version import (
    StepGetVersionsFromCMakeConfigPackageVersion,
)
from csorchestrator.frontend.step.step_create_archives import StepCreateArchives
from csorchestrator.frontend.step.step_upload_artifacts import (
    StepUploadArtifacts,
    create_artifact_prefix_from_orchestrator_name_version,
)
from csorchestrator.frontend.step.step_custom_command import StepInstallAptPackages

from csorchestrator.frontend.local_execution.step_utils import (
    StepExecuteOnlyOncePerMatrix,
    StepSkipExecutionOnLocal,
    StepExecuteOnlyOn,
)

from csorchestrator.application.factory.factory import (
    OptionalOrchestratorWithReport,
    create_orchestrator_factory_all_supported_cases,
)
from csorchestrator.application.cli.cli import orchestrator_main_with_default_run


def create_orchestrator() -> OptionalOrchestratorWithReport:
    report = Report()

    base_target_dir = Path("workspace")
    base_install_dir = base_target_dir / Path("install")
    common_repo_ref = "dev"

    repos: dict[str, None | BuildConfig] = {
        "csCMake": None,
        "csCore": BuildConfig.DEBUG_RELEASE_RELWITHDEBINFO_PARANOID,
        "csLie": BuildConfig.DEBUG_RELEASE_RELWITHDEBINFO_PARANOID,
        "csCamera": BuildConfig.DEBUG_RELEASE_RELWITHDEBINFO_PARANOID,
        "csVisOpenGL": BuildConfig.DEBUG_RELEASE_RELWITHDEBINFO_PARANOID,
    }

    o = create_orchestrator_factory_all_supported_cases(
        name="csBaseLibs", version="0.1.0", execution_matrix_name="orchestrator-matrix"
    )

    o.wf_config = WorkflowConfig(
        on_push_branches=["main", "dev"],
        on_push_tags=["'v*.*.*'"],
        on_pull_request_branches=["main"],
        on_dispatch=True,
        on_schedule=Cron.weekly(DayOfWeek.MON, hour=3),
        create_release_on_tag=ReleaseCreationOnTagConfig(name="release-from-artifacts"),
    )

    # ----------------------------------------------------------------
    p = o.create_phase("Repos Update")
    for repo in repos.keys():
        p.add_step(
            StepGetRepositoryGitHub(
                name=f"{repo} Git clone/pull-ff",
                description=f"Clone or pull-ff {repo} description",
                target_directory=(base_target_dir / repo).as_posix(),
                repo_url_parts=RepoUrlParts(
                    repo_base_url=StepGetRepositoryGitHub.GITHUB_BASE_URL_SSH,
                    repo_org="cscosine",
                    repo_name=repo + ".git",
                ),
                repo_ref=common_repo_ref,
            )
            .add_extra(
                StepGetRepositoryExtraDepthOne(
                    on_local_checkout=False,
                    on_github_action_checkout=True,
                )
            )
            .add_extra(StepExecuteOnlyOncePerMatrix())
            .add_extra(
                StepGetRepositoryExtraAccessToken("${{ secrets.ACTIONS_ORG_ACCESS }}")
            )
        )

    # ----------------------------------------------------------------
    p = o.create_phase("Install Requirements (Linux-Ubuntu)")
    p.add_step(
        StepInstallAptPackages(
            name="install apt packages",
            description="install apt packages if not already installed in the system",
            packages=[
                "libgl1-mesa-dev",
                "libopengl-dev",
                "mesa-common-dev",
            ],
            dry_run=False,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX)
        )
    )

    # ----------------------------------------------------------------
    p = o.create_phase("Get Precompiled Libraries")
    # list_3rdPartyBaseLibs = [
    #    "eigen3",
    #    "fmt",
    #    "fmt-eigen",
    #    "cpptrace",
    #    "magic_enum",
    #    "libassert",
    #    "tclap",
    #    "Catch2",
    #    "pipes",
    #    "NamedType",
    #    "tl-optional",
    #    "tl-expected",
    # ]
    #
    # for lib in list_3rdPartyBaseLibs:
    #    csGetPrecompiledLib(
    #        base_url=repo_https_url + "cscosine",
    #        repo="3rdPartyBaseLibs",
    #        libName=lib,
    #        version="v0.1.0-rc2",
    #        libs_os_presets=libs_os_presets,
    #    )
    #
    # qt_presets_mapping: Dict[str, Dict[str, str]] = {
    #    "linux": {
    #        "linux-ninja": "linux-gcc",
    #        "linux-ninja-multi-config-clang": "linux-gcc",
    #    },
    #    "windows": {
    #        "msvc2022-x64": "windows-msvc2022-x64",
    #        "msvc2022-x64-LLVM": "windows-msvc2022-x64",
    #    },
    # }
    #
    # csGetPrecompiledLib(
    #    base_url=repo_https_url + "cscosine",
    #    repo="csQt6",
    #    libName="qt6",
    #    version="v6.10.2",
    #    libs_os_presets=libs_os_presets,
    #    presets_mapping=qt_presets_mapping,
    # )
    #
    # ----------------------------------------------------------------

    p = o.create_phase("Configure-Build-Test-Install")
    for repo, config in repos.items():
        if config is not None:
            p.add_step(
                StepCMakeWorkflow(
                    name=f"{repo} CMake Workflow",
                    description=f"CMake workflow for {repo} with config: {config}",
                    source_dir=(base_target_dir / repo).as_posix(),
                    config=config,
                )
            )

    # ----------------------------------------------------------------
    p = o.create_phase("Create and Upload Artifacts")
    p.add_step(
        StepGetVersionsFromCMakeConfigPackageVersion(
            name="Get Versions",
            description="Get Versions for all libs",
            repos_auto_search_list=[
                repo for repo, config in repos.items() if config is not None
            ],
            base_install_dir=base_install_dir,
            id="versions",
            output_dict_name="packages",
        )
    )

    p.add_step(
        StepCreateArchives(
            name="Create Archives",
            description="Create archives with libs and versions",
            input_id="versions",
            input_dict="packages",
            base_install_dir=base_install_dir,
        ).add_extra(StepSkipExecutionOnLocal())
    )

    p.add_step(
        StepUploadArtifacts(
            name="Upload Artifacts",
            description="Upload Artifacts with libs and versions",
            base_install_dir=base_install_dir,
            artifact_prefix=create_artifact_prefix_from_orchestrator_name_version(o),
        )
    )

    return OptionalResultWithReport.createResultAndReport(o, report)


def main(argv: Sequence[str] | None = None) -> int:
    script_path = str(Path(__file__).resolve())
    return orchestrator_main_with_default_run(script_path, argv)


if __name__ == "__main__":
    sys.exit(main())
