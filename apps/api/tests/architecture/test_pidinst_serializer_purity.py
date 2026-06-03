"""Architecture fitness for the kernel-tier PIDINST serializer modules.

L22 / L28 of `project_pidinst_serializer_design`. The PIDINST
serializer at `cora.equipment._pidinst_serializer` and its sibling
type module `cora.equipment._pidinst_types` are pure-function CORA
infrastructure: they must never accumulate I/O, async surface,
cross-BC imports, mutable dataclass state, or `Any`-typed escape
hatches. This file is the test that prevents slice 6 (DataCite mint
adapter) work from leaking into the serializer module under deadline
pressure.

The cross-BC import test iterates `BCS - {"equipment"}` from
`tests.architecture.conftest` so the check stays in sync with the
live BC roster automatically and enforces L27 without a hand-edited
list.
"""

import ast
import typing
from pathlib import Path

import pytest

from cora.equipment._pidinst_types import (
    PidinstAlternateIdentifier,
    PidinstRecord,
    SchemaVersion,
)
from cora.equipment.aggregates.asset import AlternateIdentifierKind
from cora.equipment.errors import (
    AssetNameMissingError,
    LandingPageMissingError,
    ManufacturerStateNotAvailableError,
    OwnerStateNotAvailableError,
    PidinstRecordInvariantError,
)
from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

pytestmark = [pytest.mark.architecture]


_FORBIDDEN_IO_TOP_LEVEL_IMPORTS: frozenset[str] = frozenset(
    {
        "io",
        "asyncio",
        "aiohttp",
        "aiofiles",
        "httpx",
        "asyncpg",
        "requests",
        "psycopg",
        "psycopg2",
        "urllib",
        "socket",
        "anthropic",
        "openai",
        "boto3",
        "redis",
        "kafka",
        "subprocess",
        "tempfile",
        "shutil",
    }
)


def _pidinst_module_paths() -> list[Path]:
    tracked = tracked_python_files()
    targets = {
        CORA_ROOT / "equipment" / "_pidinst_serializer.py",
        CORA_ROOT / "equipment" / "_pidinst_types.py",
    }
    return sorted(p for p in tracked if p in targets)


def test_pidinst_serializer_imports_no_io_libraries() -> None:
    """The serializer + types modules import no I/O libraries."""
    violations: list[str] = []
    for path in _pidinst_module_paths():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in _FORBIDDEN_IO_TOP_LEVEL_IMPORTS:
                        violations.append(f"{path.name}:{node.lineno}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top in _FORBIDDEN_IO_TOP_LEVEL_IMPORTS:
                    violations.append(f"{path.name}:{node.lineno}: from {node.module} import ...")
    assert not violations, (
        "PIDINST serializer modules must stay pure (no I/O imports):\n  " + "\n  ".join(violations)
    )


def test_pidinst_serializer_has_no_async_def() -> None:
    """No `async def` in the serializer or types modules."""
    violations: list[str] = []
    for path in _pidinst_module_paths():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                violations.append(f"{path.name}:{node.lineno}: async def {node.name}")
    assert not violations, "PIDINST serializer modules must be synchronous:\n  " + "\n  ".join(
        violations
    )


def test_pidinst_serializer_imports_no_other_bc() -> None:
    """The serializer + types modules import nothing from any sibling BC.

    Iterates `BCS - {"equipment"}` to stay in sync with the live BC
    roster automatically. Enforces L27.
    """
    other_bcs = frozenset(BCS) - {"equipment"}
    violations: list[str] = []
    for path in _pidinst_module_paths():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            modules: list[tuple[int, str]] = []
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.append((node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append((node.lineno, node.module))
            for lineno, mod in modules:
                parts = mod.split(".")
                if len(parts) >= 2 and parts[0] == "cora" and parts[1] in other_bcs:
                    violations.append(f"{path.name}:{lineno}: {mod}")
    assert not violations, (
        "PIDINST serializer modules must not import sibling BCs:\n  " + "\n  ".join(violations)
    )


def test_pidinst_record_is_frozen_dataclass() -> None:
    """`PidinstRecord` carries `frozen=True` per L6."""
    params = getattr(PidinstRecord, "__dataclass_params__", None)
    assert params is not None, "PidinstRecord must be a dataclass"
    assert params.frozen is True, "PidinstRecord must be frozen=True"


def test_pidinst_record_has_no_any_or_dict_str_any_annotations() -> None:
    """L28: no `Any` and no `dict[str, Any]` in `_pidinst_types.py`.

    AST-walks every annotation (dataclass fields, function signatures,
    return types) for `Any` and `dict[str, Any]`. Either shape is a
    typing escape hatch; the intermediate is typed end to end.
    """
    types_path = CORA_ROOT / "equipment" / "_pidinst_types.py"
    tree = ast.parse(types_path.read_text())
    violations: list[str] = []

    def _is_any(node: ast.expr) -> bool:
        if isinstance(node, ast.Name) and node.id == "Any":
            return True
        return isinstance(node, ast.Attribute) and node.attr == "Any"

    def _is_dict_str_any(node: ast.expr) -> bool:
        if not isinstance(node, ast.Subscript):
            return False
        outer = node.value
        outer_name = (
            outer.id
            if isinstance(outer, ast.Name)
            else outer.attr
            if isinstance(outer, ast.Attribute)
            else None
        )
        if outer_name not in {"dict", "Dict"}:
            return False
        slc = node.slice
        if not isinstance(slc, ast.Tuple) or len(slc.elts) != 2:
            return False
        key, val = slc.elts
        key_is_str = isinstance(key, ast.Name) and key.id == "str"
        return key_is_str and _is_any(val)

    for node in ast.walk(tree):
        annotation: ast.expr | None = None
        if isinstance(node, (ast.AnnAssign, ast.arg)):
            annotation = node.annotation
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            annotation = node.returns

        if annotation is None:
            continue

        for sub in ast.walk(annotation):
            if not isinstance(sub, ast.expr):
                continue
            if _is_any(sub):
                violations.append(f"line {getattr(node, 'lineno', '?')}: Any in annotation")
                break
            if _is_dict_str_any(sub):
                violations.append(
                    f"line {getattr(node, 'lineno', '?')}: dict[str, Any] in annotation"
                )
                break

    assert not violations, (
        "_pidinst_types.py must not use Any or dict[str, Any] in annotations:\n  "
        + "\n  ".join(violations)
    )


def test_pidinst_alternate_identifier_reuses_asset_alternate_identifier_kind() -> None:
    """L13: `PidinstAlternateIdentifier.kind` is the existing
    `cora.equipment.aggregates.asset.state.AlternateIdentifierKind`, not a
    parallel enum defined inside `_pidinst_types.py`.
    """
    hints = typing.get_type_hints(PidinstAlternateIdentifier)
    assert hints["kind"] is AlternateIdentifierKind, (
        "PidinstAlternateIdentifier.kind must reuse "
        "cora.equipment.aggregates.asset.AlternateIdentifierKind"
    )

    # Belt-and-braces: assert the types module imports the existing enum.
    types_path = CORA_ROOT / "equipment" / "_pidinst_types.py"
    source = types_path.read_text()
    assert "from cora.equipment.aggregates.asset import" in source
    assert "AlternateIdentifierKind" in source


def test_pidinst_schema_version_is_pinned_to_v1_0() -> None:
    """L2: `SchemaVersion` carries exactly one member, pinned to `"1.0"`.

    A v1.1 serializer ships as a sibling function with its own constant
    enum; this enum never gains new members.
    """
    assert SchemaVersion.V1_0.value == "1.0"
    members = list(SchemaVersion)
    assert len(members) == 1, (
        f"SchemaVersion must have exactly one member at this slice; got {members}"
    )


def test_pidinst_serializer_errors_live_in_errors_module() -> None:
    """L8: the five PIDINST serializer exception classes live in
    `cora.equipment.errors`, the canonical home for cross-aggregate
    exception classes per `test_no_domain_errors_outside_aggregate_or_errors_module`.

    The `_pidinst_serializer.py` module re-exports the symbols for
    ergonomic call-site imports, but the definitions live in
    `errors.py`. This test locks the placement so the rename cannot
    silently regress.
    """
    expected_module = "cora.equipment.errors"
    classes = (
        AssetNameMissingError,
        LandingPageMissingError,
        ManufacturerStateNotAvailableError,
        OwnerStateNotAvailableError,
        PidinstRecordInvariantError,
    )
    violations = [
        f"{cls.__name__} is defined in {cls.__module__}, expected {expected_module}"
        for cls in classes
        if cls.__module__ != expected_module
    ]
    assert not violations, "\n  ".join(violations)
