"""csorchestrator configuration for csfoundation.

This module defines the authoritative project name and version as single
sources of truth, the first-party libraries of the project together with
their (cross-repo) managed dependencies, the Linux system requirements
installer, and two installation helpers:

* ``install_csfoundation_build_dependencies`` — internal use (the CI recipe in
  ``csfoundation_project.py``): installs the system requirements and downloads
  the manifest, the bundles, and only the required (pre-)compiled libraries
  from the ``third_party_base_libs`` and ``csqt6`` GitHub releases that are
  needed to *build* csfoundation from source.
* ``auto_install_csorchestrator_managed_libraries`` — customer-facing helper,
  deployed to the release via ``additional_files_list``: does everything the
  internal helper does and additionally downloads the requested prebuilt
  first-party libraries (``csCore``, ``csLie``, ...) from the ``csfoundation``
  GitHub release itself.
"""

from pathlib import Path

from csorchestrator.application.recipes.manifest_github import (
    download_csorchestrator_managed_libraries,
    install_ubuntu_apt_packages,
    resolve_library_dependencies,
)
from csorchestrator.domain.orchestrator.orchestrator import Orchestrator
from csorchestrator.foundation.core.report import Report
from csorchestrator.frontend.step.step_get_precompiled_lib_github import (
    MappingFunction,
    StepGetPrecompiledLibGithub,
)

from libs.csqt6.csorchestrator_config import (
    auto_install_csorchestrator_managed_libraries as auto_install_csqt6_libraries,
)
from libs.csqt6.csorchestrator_config import (
    qt6_mapping,
)
from libs.third_party_base_libs.csorchestrator_config import (
    auto_install_csorchestrator_managed_libraries as auto_install_third_party_base_libs_libraries,
)

# ---------------------------------------------------------------------------
# Single source of truth for the project identity.  ``csfoundation_project.py``
# imports these constants so there is exactly one place to update on release.
# ---------------------------------------------------------------------------
CSFOUNDATION_PROJECT_NAME: str = "csfoundation"
CSFOUNDATION_PROJECT_VERSION: str = "0.1.0"

# ---------------------------------------------------------------------------
# Release tags of the consumed csorchestrator-managed dependency releases.
# ---------------------------------------------------------------------------
THIRD_PARTY_BASE_LIBS_RELEASE_TAG: str = "v0.1.0"
CSQT6_RELEASE_TAG: str = "v6.11.1"
CSFOUNDATION_RELEASE_TAG: str = "v" + CSFOUNDATION_PROJECT_VERSION

# ---------------------------------------------------------------------------
# First-party libraries of this project (built from source; ``csCMake`` is
# checkout-only build tooling and intentionally not listed here) and their
# managed dependencies, derived from the "Library Dependency Graph" section of
# README.md.
#
# Dependencies are kept in one map per providing release so that each
# installer talks to exactly one release without ``if lib == "qt6"`` style
# filtering:
# * ``FIRST_PARTY_LIBRARY_DEPENDENCIES`` — internal edges between first-party
#   libraries (e.g. ``csLie -> csCore``); used to expand a request to its
#   transitive closure before per-release resolution.
# * ``THIRD_PARTY_LIBRARY_DEPENDENCIES`` — managed libraries provided by the
#   ``third_party_base_libs`` release, as needed by downstream customers
#   (test-only dependencies excluded).
# * ``THIRD_PARTY_TEST_LIBRARY_DEPENDENCIES`` — extra ``third_party_base_libs``
#   entries needed only to build & run this repo's own tests (the CI phase
#   runs Configure-Build-Test-Install). Merged in only when
#   ``include_test_dependencies=True``.
# * ``QT6_LIBRARY_DEPENDENCIES`` — managed libraries provided by the ``csqt6``
#   release (only ``csVisOpenGL`` needs ``qt6``).
#
# Transitive dependencies *internal* to a dependency release (e.g. cpptrace
# pulled in by libassert) are not repeated: they are auto-filled by the
# dependency project's own helper.
# ---------------------------------------------------------------------------
FIRST_PARTY_LIBRARIES: list[str] = [
    "csCore",
    "csLie",
    "csCamera",
    "csVisOpenGL",
]

FIRST_PARTY_LIBRARY_DEPENDENCIES: dict[str, list[str]] = {
    "csCore": [],
    "csLie": ["csCore"],
    "csCamera": ["csCore"],
    "csVisOpenGL": ["csCore"],
}

THIRD_PARTY_LIBRARY_DEPENDENCIES: dict[str, list[str]] = {
    "csCore": ["eigen3", "fmt", "fmt-eigen", "libassert", "pipes", "NamedType", "tl-expected", "tl-optional"],
    "csLie": ["eigen3"],
    "csCamera": ["eigen3"],
    "csVisOpenGL": ["eigen3"],
}

THIRD_PARTY_TEST_LIBRARY_DEPENDENCIES: dict[str, list[str]] = {
    # Catch2 is test-only: required to build & run this repo's own tests
    # (Configure-Build-Test-Install), never by downstream customers.
    # csVisOpenGL ships no tests yet, but Catch2 is listed pre-emptively
    # so the entry exists when tests are added.
    "csCore": ["Catch2"],
    "csLie": ["Catch2"],
    "csCamera": ["Catch2"],
    "csVisOpenGL": ["Catch2"],
}

QT6_LIBRARY_DEPENDENCIES: dict[str, list[str]] = {
    "csVisOpenGL": ["qt6"],
}


def install_requirements(
    orchestrator: Orchestrator,
    lib_list: list[str] | None = None,  # none means all
) -> None:
    """Install the Linux system requirements needed by the requested libraries.

    The OpenGL system packages are only required by ``csVisOpenGL``, so they
    are installed only when it is in ``lib_list`` (``None`` means all
    libraries).
    """
    if lib_list is None or "csVisOpenGL" in lib_list:
        install_ubuntu_apt_packages(
            orchestrator,
            [
                "libgl1-mesa-dev",
                "libopengl-dev",
                "mesa-common-dev",
            ],
        )


def _resolve_first_party_closure(
    required_libs: list[str] | None = None,
) -> list[str]:
    """Expand the requested first-party libraries over first-party edges.

    ``csCMake`` is checkout-only build tooling: it is dropped from explicit
    requests (it has no entry in ``FIRST_PARTY_LIBRARY_DEPENDENCIES``), and
    ``None`` means all built libraries.
    """
    if required_libs is None:
        requested = list(FIRST_PARTY_LIBRARY_DEPENDENCIES)
    else:
        requested = [lib for lib in required_libs if lib in FIRST_PARTY_LIBRARY_DEPENDENCIES]
    return resolve_library_dependencies(requested, FIRST_PARTY_LIBRARY_DEPENDENCIES) or []


def resolve_required_third_party_libraries(
    required_libs: list[str] | None = None,
    include_test_dependencies: bool = False,
) -> list[str]:
    """Resolve the ``third_party_base_libs`` libraries for the request.

    ``required_libs`` lists the first-party libraries being consumed (``None``
    means all of them). The request is first expanded over the first-party
    edges (e.g. ``csLie -> csCore``) and then over
    ``THIRD_PARTY_LIBRARY_DEPENDENCIES`` (plus
    ``THIRD_PARTY_TEST_LIBRARY_DEPENDENCIES`` when
    ``include_test_dependencies`` is ``True``). Returns only downloadable
    managed libraries (``csCMake`` build tooling never resolves to anything).
    """
    closure = _resolve_first_party_closure(required_libs)
    third_party_map: dict[str, list[str]]
    if include_test_dependencies:
        third_party_map = {
            lib: THIRD_PARTY_LIBRARY_DEPENDENCIES.get(lib, []) + THIRD_PARTY_TEST_LIBRARY_DEPENDENCIES.get(lib, [])
            for lib in FIRST_PARTY_LIBRARIES
        }
    else:
        third_party_map = THIRD_PARTY_LIBRARY_DEPENDENCIES
    expanded = resolve_library_dependencies(closure, third_party_map) or []
    return [lib for lib in expanded if lib not in FIRST_PARTY_LIBRARIES]


def resolve_required_qt6_libraries(
    required_libs: list[str] | None = None,
) -> list[str]:
    """Resolve the ``csqt6`` libraries for the request (``qt6`` iff needed)."""
    closure = _resolve_first_party_closure(required_libs)
    expanded = resolve_library_dependencies(closure, QT6_LIBRARY_DEPENDENCIES) or []
    return [lib for lib in expanded if lib not in FIRST_PARTY_LIBRARIES]


def _download_managed_libraries(
    orchestrator: Orchestrator,
    base_libs_dir: Path,
    required_libs: list[str] | None,
    org: str,
    base_url: str,
    third_party_base_libs_release_tag: str,
    qt6_release_tag: str,
    qt6_mapping_function: MappingFunction | None,
    include_test_dependencies: bool,
) -> Report:
    """Shared core: system requirements plus the per-release managed downloads."""
    report = Report()

    # Linux system requirements follow the first-party request (e.g. the
    # OpenGL packages are only needed when csVisOpenGL is being built).
    install_requirements(orchestrator, lib_list=required_libs)

    # Each release gets its own resolved list: no ``if lib == "qt6"`` filtering.
    third_party_libs = resolve_required_third_party_libraries(
        required_libs, include_test_dependencies=include_test_dependencies
    )
    if third_party_libs:
        report.append_report(
            auto_install_third_party_base_libs_libraries(
                orchestrator=orchestrator,
                release_tag=third_party_base_libs_release_tag,
                base_libs_dir=base_libs_dir,
                required_libs=third_party_libs,
                org=org,
                base_url=base_url,
            )
        )

    qt6_libs = resolve_required_qt6_libraries(required_libs)
    if qt6_libs:
        report.append_report(
            auto_install_csqt6_libraries(
                orchestrator=orchestrator,
                release_tag=qt6_release_tag,
                base_libs_dir=base_libs_dir,
                required_libs=qt6_libs,
                org=org,
                base_url=base_url,
                mapping_function=qt6_mapping_function,
            )
        )

    return report


def install_csfoundation_build_dependencies(
    orchestrator: Orchestrator,
    base_libs_dir: Path,
    required_libs: list[str] | None = None,
    org: str = "cscosine",
    base_url: str = StepGetPrecompiledLibGithub.GITHUB_BASE_URL_HTTPS,
    third_party_base_libs_release_tag: str = THIRD_PARTY_BASE_LIBS_RELEASE_TAG,
    qt6_release_tag: str = CSQT6_RELEASE_TAG,
    qt6_mapping_function: MappingFunction | None = qt6_mapping,
) -> Report:
    """Install system requirements and download the libraries needed to build.

    Internal helper used by the CI recipe in ``csfoundation_project.py`` (it
    builds csfoundation from source, so it never downloads csfoundation
    itself). Given ``required_libs`` — the first-party libraries being built
    (``None`` means all of them) — it installs the Linux system requirements,
    downloads the ``third_party_base_libs`` subset resolved via
    ``resolve_required_third_party_libraries`` (test dependencies included,
    because CI runs Configure-Build-Test-Install; internal transitive deps,
    e.g. ``cpptrace`` for ``libassert``, are auto-filled by the third-party
    helper itself), and downloads the ``csqt6`` subset resolved via
    ``resolve_required_qt6_libraries`` with ``qt6_mapping_function`` (defaults
    to ``qt6_mapping``: GCC/Ninja on Linux, MSVC 2022/Ninja on Windows; pass
    ``None`` for csorchestrator's built-in selection behaviour).

    Returns a combined ``Report`` that the caller can append to their own
    report object.
    """
    return _download_managed_libraries(
        orchestrator=orchestrator,
        base_libs_dir=base_libs_dir,
        required_libs=required_libs,
        org=org,
        base_url=base_url,
        third_party_base_libs_release_tag=third_party_base_libs_release_tag,
        qt6_release_tag=qt6_release_tag,
        qt6_mapping_function=qt6_mapping_function,
        include_test_dependencies=True,
    )


def auto_install_csorchestrator_managed_libraries(
    orchestrator: Orchestrator,
    base_libs_dir: Path,
    required_libs: list[str] | None = None,
    org: str = "cscosine",
    base_url: str = StepGetPrecompiledLibGithub.GITHUB_BASE_URL_HTTPS,
    third_party_base_libs_release_tag: str = THIRD_PARTY_BASE_LIBS_RELEASE_TAG,
    qt6_release_tag: str = CSQT6_RELEASE_TAG,
    csfoundation_release_tag: str = CSFOUNDATION_RELEASE_TAG,
    qt6_mapping_function: MappingFunction | None = qt6_mapping,
) -> Report:
    """Download prebuilt csfoundation libraries and everything they need.

    Customer-facing helper, deployed to the release via
    ``additional_files_list``. Given ``required_libs`` — the first-party
    libraries being consumed (``None`` means all of them) — it installs the
    build dependencies (system requirements plus the ``third_party_base_libs``
    / ``csqt6`` managed libraries, test-only Catch2 never included) via
    ``install_csfoundation_build_dependencies`` and then downloads the
    requested prebuilt first-party libraries (``csCore``, ``csLie``, ...)
    from the ``csfoundation`` GitHub release itself, so downstream projects
    consume binaries instead of building from source.

    Returns a combined ``Report`` that the caller can append to their own
    report object.
    """
    report = _download_managed_libraries(
        orchestrator=orchestrator,
        base_libs_dir=base_libs_dir,
        required_libs=required_libs,
        org=org,
        base_url=base_url,
        third_party_base_libs_release_tag=third_party_base_libs_release_tag,
        qt6_release_tag=qt6_release_tag,
        qt6_mapping_function=qt6_mapping_function,
        include_test_dependencies=False,
    )

    first_party_libs = _resolve_first_party_closure(required_libs)
    downloadable = [lib for lib in first_party_libs if lib in FIRST_PARTY_LIBRARY_DEPENDENCIES]
    if downloadable:
        report.append_report(
            download_csorchestrator_managed_libraries(
                orchestrator=orchestrator,
                base_url=base_url,
                org=org,
                git_repo=CSFOUNDATION_PROJECT_NAME,
                project_name=CSFOUNDATION_PROJECT_NAME,
                project_version=CSFOUNDATION_PROJECT_VERSION,
                release_tag=csfoundation_release_tag,
                base_libs_dir=base_libs_dir,
                lib_name_list=downloadable,
                library_dependencies=FIRST_PARTY_LIBRARY_DEPENDENCIES,
            )
        )

    return report
