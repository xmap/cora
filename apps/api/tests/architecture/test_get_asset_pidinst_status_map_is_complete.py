"""Architecture fitness: every PIDINST serializer error has an HTTP handler.

Per L15 of project_asset_persistent_id_design. Equipment's
`register_equipment_routes` MUST register an `add_exception_handler`
for each of the five `PidinstSerializationError` subclasses (or
intentionally leave `PidinstRecordInvariantError` to FastAPI's
default 500). This AST-walks `equipment/routes.py` for actual
`add_exception_handler` Call sites (not just bare Name references)
so a dangling import or unused alias does not satisfy the assertion.
"""

import ast

import pytest

from cora.equipment.errors import (
    AssetNameMissingError,
    LandingPageMissingError,
    ManufacturerStateNotAvailableError,
    OwnerStateNotAvailableError,
    PidinstRecordInvariantError,
)
from tests.architecture.conftest import CORA_ROOT

pytestmark = [pytest.mark.architecture]

_REGISTERED_HANDLERS = {
    OwnerStateNotAvailableError.__name__,
    ManufacturerStateNotAvailableError.__name__,
    LandingPageMissingError.__name__,
    AssetNameMissingError.__name__,
}
_UNREGISTERED_BY_DESIGN = {PidinstRecordInvariantError.__name__}


def _registered_exception_classes(tree: ast.Module) -> set[str]:
    """Extract every class name actually passed to add_exception_handler.

    Two source patterns are covered:

      app.add_exception_handler(SomeError, handler_fn)

      for cls in (Error1, Error2):
          app.add_exception_handler(cls, handler_fn)

    For the loop pattern, the For node's iter is a Tuple whose
    elements are the registered classes. For the direct pattern, the
    Call's first positional arg is the class.
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


def test_get_asset_pidinst_status_map_is_complete() -> None:
    """Every PIDINST serializer error that L8 maps to a non-500 status
    code is actually wired via add_exception_handler in routes.py.

    Tighter than walking bare ast.Name nodes (the old check could be
    satisfied by a dangling import or unused alias); this walks the
    Call sites that register the handlers, so the assertion only
    passes when the registration actually wires.
    """
    routes_path = CORA_ROOT / "equipment" / "routes.py"
    tree = ast.parse(routes_path.read_text())
    registered = _registered_exception_classes(tree)

    missing = _REGISTERED_HANDLERS - registered
    assert not missing, (
        "Equipment routes.py is missing add_exception_handler "
        f"registration for PIDINST error class(es): {sorted(missing)}. "
        "Tighten the registration loop or amend L8 + L9 in "
        "project_asset_persistent_id_design.md."
    )

    accidentally_registered = _UNREGISTERED_BY_DESIGN & registered
    assert not accidentally_registered, (
        "PidinstRecordInvariantError MUST NOT be wired to a custom handler "
        "(it is a defensive construction-time invariant; FastAPI default 500 "
        "is the correct outcome). Found registered in routes.py: "
        f"{sorted(accidentally_registered)}"
    )
