"""Toolchain and compiler mapping configuration for third_party_base_libs.

This module defines the authoritative project name and version as single
sources of truth, and provides the ``auto_install_csorchestrator_managed_libraries``
helper that client projects can use to download the manifest, the bundle, and the
selected (pre-)compiled libraries from a GitHub release with minimal boilerplate.
"""

from pathlib import Path

from csorchestrator.application.recipes.manifest_github import (
    download_csorchestrator_managed_libraries,
)
from csorchestrator.domain.orchestrator.orchestrator import Orchestrator
from csorchestrator.foundation.core.report import Report
from csorchestrator.frontend.step.step_get_precompiled_lib_github import (
    MappingFunction,
    StepGetPrecompiledLibGithub,
)

# ---------------------------------------------------------------------------
# Single source of truth for the project identity.  ``third_party_base_libs_project.py``
# imports these constants so there is exactly one place to update on release.
# ---------------------------------------------------------------------------
THIRD_PARTY_BASE_LIBS_PROJECT_NAME: str = "third_party_base_libs"
THIRD_PARTY_BASE_LIBS_PROJECT_VERSION: str = "0.1.0"

# ---------------------------------------------------------------------------
# Authoritative list of library dependencies, derived from the
# "Library Dependency Graph" section of README.md.
#
# Only **link-time / compile-time** dependencies are listed here.  Test-only
# dependencies (e.g. pipes -> Catch2) are intentionally excluded -- they are
# documented as dotted arrows in the README and are not required for a normal
# downstream consumer.
# ---------------------------------------------------------------------------
LIBRARY_DEPENDENCIES: dict[str, list[str]] = {
    "fmt-eigen": ["eigen3", "fmt"],
    "libassert": ["cpptrace"],
}


def auto_install_csorchestrator_managed_libraries(
    orchestrator: Orchestrator,
    release_tag: str,
    base_libs_dir: Path,
    required_libs: list[str] | None = None,
    org: str = "cscosine",
    git_repo: str = THIRD_PARTY_BASE_LIBS_PROJECT_NAME,
    base_url: str = StepGetPrecompiledLibGithub.GITHUB_BASE_URL_HTTPS,
    mapping_function: MappingFunction | None = None,
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
      ``LIBRARY_DEPENDENCIES``): requesting ``["fmt-eigen"]`` also pulls in
      ``eigen3`` and ``fmt``.
    * Accepts an optional ``mapping_function`` (default ``None``) that is
      propagated verbatim to ``download_csorchestrator_managed_libraries``
      (and from there to each ``StepGetPrecompiledLibGithub``).  Use it when
      the consumer toolchain matrix does not exactly match the variant
      strings the bundle was published with (e.g. map a local-only compiler
      / generator to the closest published precompiled variant, or return
      ``None`` to skip an unsupported matrix entry).
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
        project_name=THIRD_PARTY_BASE_LIBS_PROJECT_NAME,
        project_version=THIRD_PARTY_BASE_LIBS_PROJECT_VERSION,
        release_tag=release_tag,
        base_libs_dir=base_libs_dir,
        lib_name_list=required_libs or None,
        library_dependencies=LIBRARY_DEPENDENCIES,
        mapping_function=mapping_function,
    )
