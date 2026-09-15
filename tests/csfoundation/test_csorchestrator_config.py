from csfoundation.csorchestrator_config import (
    FIRST_PARTY_LIBRARIES,
    FIRST_PARTY_LIBRARY_DEPENDENCIES,
    QT6_LIBRARY_DEPENDENCIES,
    THIRD_PARTY_LIBRARY_DEPENDENCIES,
    THIRD_PARTY_TEST_LIBRARY_DEPENDENCIES,
    resolve_required_qt6_libraries,
    resolve_required_third_party_libraries,
)


def test_all_built_first_party_libraries_are_declared() -> None:
    # every built first-party library is declared (csCMake is checkout-only
    # build tooling and intentionally absent from all maps).
    assert set(FIRST_PARTY_LIBRARY_DEPENDENCIES) == set(FIRST_PARTY_LIBRARIES)
    assert set(THIRD_PARTY_LIBRARY_DEPENDENCIES) <= set(FIRST_PARTY_LIBRARIES)
    assert set(THIRD_PARTY_TEST_LIBRARY_DEPENDENCIES) == set(FIRST_PARTY_LIBRARIES)
    assert "csCMake" not in FIRST_PARTY_LIBRARIES


def test_qt6_is_only_required_by_csvisopengl() -> None:
    assert set(QT6_LIBRARY_DEPENDENCIES) == {"csVisOpenGL"}
    assert resolve_required_qt6_libraries(["csLie"]) == []
    assert resolve_required_qt6_libraries(["csVisOpenGL"]) == ["qt6"]


def test_catch2_is_test_only() -> None:
    for deps in THIRD_PARTY_LIBRARY_DEPENDENCIES.values():
        assert "Catch2" not in deps
    # customer view excludes Catch2; internal/CI view includes it.
    assert "Catch2" not in resolve_required_third_party_libraries(None)
    assert "Catch2" not in resolve_required_third_party_libraries(["csCamera"])
    assert "Catch2" in resolve_required_third_party_libraries(None, include_test_dependencies=True)
    assert "Catch2" in resolve_required_third_party_libraries(["csCamera"], include_test_dependencies=True)


def test_resolve_cscamera_does_not_require_qt6() -> None:
    internal = resolve_required_third_party_libraries(["csCamera"], include_test_dependencies=True)
    customer = resolve_required_third_party_libraries(["csCamera"])

    assert internal == sorted(internal)
    # csCamera transitively needs what csCore needs; the internal view adds
    # the test-only Catch2 pulled by csCamera itself for its tests.
    assert set(customer) == {
        "NamedType",
        "eigen3",
        "fmt",
        "fmt-eigen",
        "libassert",
        "pipes",
        "tl-expected",
        "tl-optional",
    }
    assert set(internal) == set(customer) | {"Catch2"}
    assert resolve_required_qt6_libraries(["csCamera"]) == []


def test_resolve_csvisopengl_requires_qt6() -> None:
    internal = resolve_required_third_party_libraries(["csVisOpenGL"], include_test_dependencies=True)
    customer = resolve_required_third_party_libraries(["csVisOpenGL"])

    assert set(customer) == set(resolve_required_third_party_libraries(["csCamera"]))
    assert set(internal) == set(customer) | {"Catch2"}
    assert resolve_required_qt6_libraries(["csVisOpenGL"]) == ["qt6"]


def test_resolve_none_means_all_libraries() -> None:
    assert set(resolve_required_third_party_libraries(None)) == set(
        resolve_required_third_party_libraries(["csCore", "csLie", "csCamera", "csVisOpenGL"])
    )
    assert set(resolve_required_third_party_libraries(None, include_test_dependencies=True)) == set(
        resolve_required_third_party_libraries(
            ["csCore", "csLie", "csCamera", "csVisOpenGL"], include_test_dependencies=True
        )
    )


def test_resolve_unknown_first_party_library_requires_nothing() -> None:
    # csCMake is checkout-only build tooling: unknown to the dependency maps,
    # so it resolves to nothing rather than failing.
    assert resolve_required_third_party_libraries(["csCMake"]) == []
    assert resolve_required_qt6_libraries(["csCMake"]) == []
