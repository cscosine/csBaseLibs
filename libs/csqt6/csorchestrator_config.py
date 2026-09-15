"""Toolchain and compiler mapping configuration for csqt6.

This module defines the authoritative project name and version as single
sources of truth, keeps the toolchain mapping used by the build recipe, and
provides the ``auto_install_csorchestrator_managed_libraries`` helper that
client projects can use to download the manifest, the bundle, and the
selected (pre-)compiled Qt libraries from a GitHub release with minimal
boilerplate.
"""

from pathlib import Path

from csorchestrator.application.recipes.manifest_github import (
    download_csorchestrator_managed_libraries,
)
from csorchestrator.domain.context.context_compiler_generator import (
    Compiler,
    ContextCompilerGenerator,
    GeneratorWithType,
)
from csorchestrator.domain.context.context_os_architecture import OS
from csorchestrator.domain.context.context_os_architecture_compiler_generator import (
    ContextOsArchitectureCompilerGenerator,
)
from csorchestrator.domain.orchestrator.orchestrator import Orchestrator
from csorchestrator.foundation.core.report import Report
from csorchestrator.frontend.step.step_get_precompiled_lib_github import (
    MappingFunction,
    StepGetPrecompiledLibGithub,
)

# ---------------------------------------------------------------------------
# Single source of truth for the project identity.  ``csqt6_project.py``
# imports these constants so there is exactly one place to update on release.
# Please keep the version aligned with the Qt release being built.
# ---------------------------------------------------------------------------
CSQT6_PROJECT_NAME: str = "csqt6"
CSQT6_PROJECT_VERSION: str = "6.11.1"

# ---------------------------------------------------------------------------
# Authoritative list of library dependencies.
#
# The Qt 6 build is a self-contained, single-source project: the qt6
# repository does not depend on any other csorchestrator-managed library,
# so this map is intentionally empty.  It is kept here so the auto-install
# helper stays drop-in compatible with the csorchestrator download API (and
# so future dependencies can be added without touching the helper).
# ---------------------------------------------------------------------------
LIBRARY_DEPENDENCIES: dict[str, list[str]] = {}


def qt6_mapping(
    context: ContextOsArchitectureCompilerGenerator,
) -> ContextOsArchitectureCompilerGenerator | None:
    if context.context_os_architecture.os == OS.LINUX:
        new_context = context
        new_context.context_compiler_generator = ContextCompilerGenerator(
            compiler_family=Compiler.GCC,
            compiler_version=ContextCompilerGenerator.COMPILER_VERSION_DEFAULT,
            build_generator=GeneratorWithType.NINJA,
        )
        return new_context
    elif context.context_os_architecture.os == OS.WINDOWS:
        new_context = context
        new_context.context_compiler_generator = ContextCompilerGenerator(
            compiler_family=Compiler.MSVC,
            compiler_version=ContextCompilerGenerator.COMPILER_VERSION_MSVC_2022_17,
            build_generator=GeneratorWithType.NINJA,
        )
        return new_context
    return None


def auto_install_csorchestrator_managed_libraries(
    orchestrator: Orchestrator,
    release_tag: str,
    base_libs_dir: Path,
    required_libs: list[str] | None = None,
    org: str = "cscosine",
    git_repo: str = CSQT6_PROJECT_NAME,
    base_url: str = StepGetPrecompiledLibGithub.GITHUB_BASE_URL_HTTPS,
    mapping_function: MappingFunction | None = qt6_mapping,
) -> Report:
    """Download the manifest, the bundle, and the requested managed libraries.

    This is a convenience wrapper around
    ``download_csorchestrator_managed_libraries`` that:

    * Uses **sensible defaults** for the repository identity (org, git repo,
      project name / version) so consumer code only has to pass the two
      genuinely variable arguments: ``release_tag`` and ``base_libs_dir``.
    * Accepts an optional ``required_libs`` list.  When provided, missing
      dependencies are **auto-filled transitively** by csorchestrator itself
      (via the ``library_dependencies`` parameter, sourced from
      ``LIBRARY_DEPENDENCIES``).  For csqt6 the map is empty because the Qt 6
      build has no csorchestrator-managed library dependencies, but the
      mechanism is wired in for future use.
    * Accepts an optional ``mapping_function`` (defaults to ``qt6_mapping``,
      the toolchain mapping defined in this file) used to select the prebuilt
      variant matching the consuming platform (OS / architecture / compiler /
      generator) from the release matrix.  Pass ``None`` to fall back to
      csorchestrator's built-in selection behaviour.
    * Returns a combined ``Report`` that the caller can append to their own
      report object.
    """

    # ------------------------------------------------------------------
    # Delegate to the csorchestrator download helper (manifest + bundle + libs).
    # Transitive dependency auto-fill is performed inside csorchestrator via
    # the ``library_dependencies`` mapping.
    # ------------------------------------------------------------------
    return download_csorchestrator_managed_libraries(
        orchestrator=orchestrator,
        base_url=base_url,
        org=org,
        git_repo=git_repo,
        project_name=CSQT6_PROJECT_NAME,
        project_version=CSQT6_PROJECT_VERSION,
        release_tag=release_tag,
        base_libs_dir=base_libs_dir,
        lib_name_list=required_libs or None,
        library_dependencies=LIBRARY_DEPENDENCIES,
        mapping_function=mapping_function,
    )
