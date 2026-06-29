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
from csorchestrator.domain.context.context_os_architecture import (
    UBUNTU_STRING_PREFIX,
    UBUNTU_VERSIONS,
)

from csorchestrator.domain.context.context_os_architecture_compiler_generator import (
    ContextOsArchitectureCompilerGenerator,
)
from csorchestrator.domain.context.context_compiler_generator import (
    ContextCompilerGenerator,
    Compiler,
    GeneratorWithType,
)

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
from csorchestrator.frontend.step.step_custom_command import StepInstallAptPackages, StepWinPSCommand
from csorchestrator.frontend.step.step_get_precompiled_lib_github import (
    StepGetPrecompiledLibGithub,
)

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
    base_libs_dir = base_target_dir / Path("libs")
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
    p = o.create_phase("Enable long paths (Windows)")
    p.add_step(
        StepWinPSCommand(
            name="enable long paths",
            description="enable long paths",
            cmd = [
                "Set-ItemProperty `",
                ' -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\FileSystem" `',
                " -Name LongPathsEnabled `",
                " -Value 1",
                "",
                '$v = [int](Get-ItemProperty "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\FileSystem").LongPathsEnabled',
                'if ($v -ne 1) {',
                '    throw "LongPathsEnabled is NOT enabled (value = $v)"',
                '}',
            ],
            dry_run=False,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(StepSkipExecutionOnLocal())
        .add_extra(
            StepExecuteOnlyOn(os=OS.WINDOWS)
        )
    )

    # ----------------------------------------------------------------
    p = o.create_phase("Get Precompiled Libraries")

    list_3rdPartyBaseLibs: dict[str, str] = {
        "eigen3": "3.4.0",
        "fmt": "11.2.1",
        "fmt-eigen": "1.0.0",
        "cpptrace": "0.8.3",
        "magic_enum": "0.9.7",
        "libassert": "2.1.5",
        "tclap": "1.0.0",
        "Catch2": "3.10.0",
        "pipes": "0.0.1",
        "NamedType": "1.1.0",
        "tl-expected": "1.2.0",
        "tl-optional": "1.0.0",
    }

    for lib_name, lib_version in list_3rdPartyBaseLibs.items():
        p.add_step(
            StepGetPrecompiledLibGithub(
                name=f"Get Precompiled Lib {lib_name} from 3rdPartyBaseLibs",
                description="get precompiled lib from github release",
                base_url=StepGetPrecompiledLibGithub.GITHUB_BASE_URL_HTTPS,
                org="cscosine",
                project_name="3rdPartyBaseLibs",
                project_tag="v0.1.0-test",
                lib_name=lib_name,
                lib_version=lib_version,
                base_libs_dir=base_libs_dir,
            )
        )

    def qt6_mapping(
        context: ContextOsArchitectureCompilerGenerator,
    ) -> ContextOsArchitectureCompilerGenerator | None:
        if context.context_os_architecture.os == OS.LINUX:
            if (
                context.context_os_architecture.os_version
                == UBUNTU_VERSIONS.UBUNTU_22_04.value
                or context.context_os_architecture.os_version
                == UBUNTU_VERSIONS.UBUNTU_24_04.value
            ):
                newContext = context
                newContext.context_compiler_generator = ContextCompilerGenerator(
                    compiler_family=Compiler.GCC,
                    compiler_version=ContextCompilerGenerator.COMPILER_VERSION_DEFAULT,
                    build_generator=GeneratorWithType.NINJA,
                )
                return newContext
        elif context.context_os_architecture.os == OS.WINDOWS:
            newContext = context
            newContext.context_compiler_generator = ContextCompilerGenerator(
                compiler_family=Compiler.MSVC,
                compiler_version=ContextCompilerGenerator.COMPILER_VERSION_MSVC_2022_17,
                build_generator=GeneratorWithType.NINJA,
            )
            return newContext
        return None

    p.add_step(
        StepGetPrecompiledLibGithub(
            name="Get Precompiled Lib qt6",
            description="get precompiled lib from github release",
            base_url=StepGetPrecompiledLibGithub.GITHUB_BASE_URL_HTTPS,
            org="cscosine",
            project_name="csQt6",
            project_tag="v6.11.1",
            lib_name="qt6",
            lib_version="v6.11.1",
            base_libs_dir=base_libs_dir,
            mapping_function=qt6_mapping,
        )
    )

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
