"""Architecture fitness: the closure-proof suite must exist.

Per memo section 16 R4 of project_asset_persistent_id_design.
The slice-C serializer becomes dead code on main if no production
caller exercises it. Slice E.1 ships the closure-proof integration
suite at `tests/integration/test_get_asset_pidinst_handler_postgres.py`
plus the HTTP-level contract suite at
`tests/contract/test_get_asset_pidinst_endpoint.py` precisely to
prevent that regression.

This fitness asserts:
  - The handler-level integration suite file exists, parses, and
    contains at least 12 async test functions whose names start with
    `test_pidinst_route_` (per memo section 8 enumeration).
  - The HTTP-level contract suite file exists, parses, and contains
    at least 4 sync test functions whose names start with
    `test_get_asset_pidinst_` (the orthogonal HTTP-layer check).

If either file is quarantined (renamed, deleted, or emptied), this
test fails and the merge is blocked.
"""

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architecture]

_API_ROOT = Path(__file__).resolve().parents[2]
_INTEGRATION_SUITE = (
    _API_ROOT / "tests" / "integration" / "test_get_asset_pidinst_handler_postgres.py"
)
_CONTRACT_SUITE = _API_ROOT / "tests" / "contract" / "test_get_asset_pidinst_endpoint.py"


def _async_test_function_names(tree: ast.Module, prefix: str) -> list[str]:
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith(prefix)
    ]


def _sync_test_function_names(tree: ast.Module, prefix: str) -> list[str]:
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith(prefix)
    ]


def test_get_asset_pidinst_handler_postgres_suite_is_present() -> None:
    assert _INTEGRATION_SUITE.exists(), (
        f"Closure-proof handler-level integration suite missing at "
        f"{_INTEGRATION_SUITE}. Slice E.1 ships this file per memo L11; "
        "removing it makes slice-C serializer code dead on main."
    )
    tree = ast.parse(_INTEGRATION_SUITE.read_text())
    test_names = _async_test_function_names(tree, "test_pidinst_route_")
    assert len(test_names) >= 12, (
        f"Closure-proof integration suite at {_INTEGRATION_SUITE} declares "
        f"only {len(test_names)} test functions; memo section 8 enumerates "
        "12 (6 happy + 4 negative + 2 closure-proof). Found: "
        f"{sorted(test_names)}"
    )


def test_get_asset_pidinst_endpoint_contract_suite_is_present() -> None:
    assert _CONTRACT_SUITE.exists(), (
        f"HTTP-level contract suite missing at {_CONTRACT_SUITE}. "
        "Slice E.1 ships this file alongside the handler-level suite to "
        "pin the L9 exception-handler-tuple registrations + L7 route path. "
        "Removing it allows a regression that drops the tuple to pass "
        "silently."
    )
    tree = ast.parse(_CONTRACT_SUITE.read_text())
    test_names = _sync_test_function_names(tree, "test_get_asset_pidinst_")
    assert len(test_names) >= 4, (
        f"HTTP-level contract suite at {_CONTRACT_SUITE} declares only "
        f"{len(test_names)} test functions; expected at least 4 covering "
        "the 404 / 409 (owners) / 409 (manufacturer) / route-path locks. "
        f"Found: {sorted(test_names)}"
    )
