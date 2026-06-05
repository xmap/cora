"""Architecture fitness: Fixture-tier PIDINST module + error placement.

Per Section 15.4 + Section 20 R3 of project_fixture_pidinst_design:

  - `FixturePidinstView` lives in `cora.equipment._pidinst_types`
    alongside `AssetPidinstView` per Lock 1; the Fixture-tier view
    must not drift into a sibling slice module.
  - `to_fixture_pidinst_record` lives in `cora.equipment._pidinst_serializer`
    alongside `to_pidinst_record`; the sibling serializer must share
    the same BC-root module so the kernel reuse stays one import away.
  - Four concrete `FixturePidinstSerializationError` subclasses
    (`FixtureOwnerStateNotAvailableError`,
    `FixtureManufacturerStateNotAvailableError`,
    `FixtureLandingPageMissingError`, `FixtureNameMissingError`) all
    inherit from `FixturePidinstSerializationError` which in turn
    inherits from the cross-tier `PidinstSerializationError` base so
    a generic `except PidinstSerializationError` clause continues to
    catch both Asset-tier and Fixture-tier failures per Section 10.3.
  - Each of the four concrete classes is wired via
    `add_exception_handler` in `equipment/routes.py` so the Section
    13 status-code map (409 owner / 409 manufacturer / 422 landing
    page / 422 name) actually fires at the HTTP boundary.
"""

import ast

import pytest

from cora.equipment._pidinst_serializer import to_fixture_pidinst_record
from cora.equipment._pidinst_types import FixturePidinstView
from cora.equipment.errors import (
    FixtureLandingPageMissingError,
    FixtureManufacturerStateNotAvailableError,
    FixtureNameMissingError,
    FixtureOwnerStateNotAvailableError,
    FixturePidinstSerializationError,
    PidinstSerializationError,
)
from tests.architecture.conftest import CORA_ROOT

pytestmark = [pytest.mark.architecture, pytest.mark.timeout(60, method="thread")]

_CONCRETE_FIXTURE_ERRORS: tuple[type[FixturePidinstSerializationError], ...] = (
    FixtureOwnerStateNotAvailableError,
    FixtureManufacturerStateNotAvailableError,
    FixtureLandingPageMissingError,
    FixtureNameMissingError,
)


def _registered_exception_classes(tree: ast.Module) -> set[str]:
    """Extract every class name passed to `add_exception_handler`.

    Mirrors the helper in
    `test_get_asset_pidinst_status_map_is_complete.py`. Covers both
    the direct `app.add_exception_handler(SomeError, handler_fn)`
    call and the `for cls in (Error1, Error2): ...` loop pattern that
    `equipment/routes.py` uses to collapse same-shape registrations.
    """
    registered: set[str] = set()
    add_handler_calls: list[ast.Call] = []
    for_loops_with_handler: list[ast.For] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "add_exception_handler":
                add_handler_calls.append(node)
        elif isinstance(node, ast.For):
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "add_exception_handler"
                ):
                    for_loops_with_handler.append(node)
                    break

    for call in add_handler_calls:
        if not call.args:
            continue
        first = call.args[0]
        if isinstance(first, ast.Name):
            registered.add(first.id)

    for loop in for_loops_with_handler:
        iter_node = loop.iter
        if isinstance(iter_node, ast.Tuple):
            for elt in iter_node.elts:
                if isinstance(elt, ast.Name):
                    registered.add(elt.id)

    return registered


def test_fixture_pidinst_view_lives_in_pidinst_types_module() -> None:
    assert FixturePidinstView.__module__ == "cora.equipment._pidinst_types", (
        "FixturePidinstView must live in cora.equipment._pidinst_types "
        "alongside AssetPidinstView per Section 9.1 Lock 1. Found in: "
        f"{FixturePidinstView.__module__!r}"
    )


def test_to_fixture_pidinst_record_lives_in_designated_serializer_file() -> None:
    assert to_fixture_pidinst_record.__module__ == "cora.equipment._pidinst_serializer", (
        "to_fixture_pidinst_record must live in cora.equipment._pidinst_serializer "
        "alongside to_pidinst_record per Section 10.1 Lock 1. Found in: "
        f"{to_fixture_pidinst_record.__module__!r}"
    )


def test_fixture_pidinst_serialization_error_inherits_pidinst_serialization_error_base() -> None:
    mro: tuple[type, ...] = FixturePidinstSerializationError.__mro__
    assert issubclass(FixturePidinstSerializationError, PidinstSerializationError), (
        "FixturePidinstSerializationError must inherit from the cross-tier "
        "PidinstSerializationError base per Section 10.3 so generic exception "
        "handlers continue to catch both Asset-tier and Fixture-tier failures. "
        f"MRO: {[cls.__name__ for cls in mro]}"
    )


@pytest.mark.parametrize("error_cls", _CONCRETE_FIXTURE_ERRORS, ids=lambda c: c.__name__)
def test_fixture_pidinst_concrete_error_inherits_fixture_pidinst_serialization_error_base(
    error_cls: type[FixturePidinstSerializationError],
) -> None:
    assert issubclass(error_cls, FixturePidinstSerializationError), (
        f"{error_cls.__name__} must inherit from FixturePidinstSerializationError "
        "per Section 10.3 so the cross-tier `except PidinstSerializationError` "
        f"clause catches it. MRO: {[cls.__name__ for cls in error_cls.__mro__]}"
    )


def test_fixture_pidinst_concrete_errors_each_register_as_http_handler() -> None:
    routes_path = CORA_ROOT / "equipment" / "routes.py"
    tree = ast.parse(routes_path.read_text())
    registered = _registered_exception_classes(tree)

    expected = {cls.__name__ for cls in _CONCRETE_FIXTURE_ERRORS}
    missing = expected - registered
    assert not missing, (
        "Equipment routes.py is missing add_exception_handler registration "
        f"for Fixture-tier PIDINST error class(es): {sorted(missing)} per "
        "Section 13 status-code map (409 owner + 409 manufacturer + 422 "
        "landing page + 422 name)."
    )
