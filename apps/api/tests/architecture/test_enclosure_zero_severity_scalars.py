"""Pin: Enclosure aggregate state + event payloads carry zero severity-
scalar fields. ERROR mode, CI-blocking, no allowlist.

D9-L1 (anti-lock per [[project_enclosure_stage1_design]]) forbids
severity scalars on the Enclosure aggregate. The Enclosure BC models a
single observation axis (`permit_status`) with a closed enum
(`Permitted` / `NotPermitted` / `Unknown`); operator severity scoring,
SIL ratings, signal words, vendor status codes, and any other numeric
or string risk-grading scalar belong to the operator's decision layer,
not the aggregate. Smuggling a `severity` / `risk_level` / `sil_level`
field onto Enclosure state or event payloads would silently widen the
observation axis past its locked single-axis posture and contaminate the
projection-only permit envelope with grading data.

The fitness walks every field declared on a frozen dataclass under
`apps/api/src/cora/enclosure/aggregates/**/{state,events}.py` and fails
on any field name matching the forbidden-token regex below
(case-insensitive). Scope is intentionally narrow: only the aggregate
kernel files where the lock binds; ports, projections, and the
permit-observation envelope are pinned by separate fitness tests in
later sub-slices.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


_ENCLOSURE_AGGREGATE_FILE_PATTERN = re.compile(
    r"/enclosure/aggregates/(?:[a-z_][a-z0-9_]*/)+(?:state|events)\.py$"
)

_FORBIDDEN_FIELD_TOKEN = re.compile(
    r"(?i)(severity|risk_level|criticality|sil(_level)?|hazard_level|signal_word|vendor_status_code)"
)


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _is_frozen_dataclass_decorator(decorator: ast.expr) -> bool:
    """True for `@dataclass(frozen=True)` (call form with the literal True)."""
    if not isinstance(decorator, ast.Call):
        return False
    func = decorator.func
    name = (
        func.id
        if isinstance(func, ast.Name)
        else func.attr
        if isinstance(func, ast.Attribute)
        else None
    )
    if name != "dataclass":
        return False
    frozen_kw = next((kw for kw in decorator.keywords if kw.arg == "frozen"), None)
    if frozen_kw is None:
        return False
    return isinstance(frozen_kw.value, ast.Constant) and frozen_kw.value.value is True


def _has_frozen_dataclass_decorator(class_def: ast.ClassDef) -> bool:
    return any(_is_frozen_dataclass_decorator(d) for d in class_def.decorator_list)


def _frozen_dataclasses(tree: ast.AST) -> list[ast.ClassDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and _has_frozen_dataclass_decorator(node)
    ]


def _class_field_names(class_def: ast.ClassDef) -> list[tuple[int, str]]:
    """Return (lineno, name) for every annotated assignment in the class body."""
    out: list[tuple[int, str]] = []
    for node in class_def.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.append((node.lineno, node.target.id))
    return out


def _enclosure_aggregate_files() -> list[Path]:
    return sorted(
        path
        for path in tracked_python_files()
        if _ENCLOSURE_AGGREGATE_FILE_PATTERN.search(str(path)) is not None
    )


@pytest.mark.architecture
@pytest.mark.parametrize("path", _enclosure_aggregate_files(), ids=_qualified)
def test_enclosure_aggregate_carries_no_severity_scalar_field(path: Path) -> None:
    """Every frozen-dataclass field on Enclosure aggregate state and event
    payloads MUST have a field name free of the forbidden severity-scalar
    tokens. Zero hits expected; no allowlist."""
    tree = ast.parse(path.read_text())

    offenders: list[str] = []
    for cls in _frozen_dataclasses(tree):
        for lineno, name in _class_field_names(cls):
            match = _FORBIDDEN_FIELD_TOKEN.search(name)
            if match is None:
                continue
            offenders.append(
                f"line {lineno}: {cls.name}.{name} matches forbidden "
                f"severity-scalar token {match.group(0)!r}"
            )

    assert not offenders, (
        f"{_qualified(path)} violates the D9-L1 zero-severity-scalar lock:\n  "
        + "\n  ".join(offenders)
        + "\n\nEnclosure models a single observation axis (`permit_status`) "
        "with a closed enum. Severity, risk_level, criticality, sil_level, "
        "hazard_level, signal_word, and vendor_status_code fields are "
        "forbidden on aggregate state and event payloads. See "
        "`project_enclosure_stage1_design.md` anti-lock D9-L1."
    )
