"""Procedure-kind naming convention fitness function.

Enforces the convention in docs/architecture/modules/operation/index.md:
a deployment Procedure ``kind`` reads ``<subject>_<operation-noun>`` with
the operation noun LAST, never a leading imperative verb. The operation
noun is the Capability family the procedure realizes, or a sharper
operation within it (``homing`` / ``centering`` under ``maintenance`` /
``alignment``). A value-named act (``*_calibration``) is also rejected:
the act is a ``*_characterization`` and the value it yields is a
Calibration quantity.

Scope: scenario tests under ``tests/integration/scenarios/``, which carry
the deployment-representative procedure vocabulary. Unit / contract tests
use throwaway placeholder kinds (``bakeout``, ``alignment``, ``a``,
padded whitespace for trim/reject validation) that exercise the aggregate
mechanics, not deployment naming, so they are deliberately out of scope.

Growth: when a genuinely new operation noun lands, add it to
``APPROVED_OPERATION_NOUNS`` in the same PR (the noun-LAST allowlist, like
the calibration-quantity catalog). Whole-kind carve-outs (milestones,
capture-and-store idioms) go in ``CARVE_OUT_KINDS`` with a rationale.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import tracked_test_files

if TYPE_CHECKING:
    from pathlib import Path

# Nouns that may be the LAST token of a procedure kind. Each is a noun
# (gerund / -tion / -ment / established operation-noun), not a verb.
APPROVED_OPERATION_NOUNS = frozenset(
    {
        "alignment",
        "centering",
        "characterization",
        "homing",
        "reboot",
        "setting",
        "change",
    }
)

# Whole-kind carve-outs, with rationale:
#   first_light            - whole-system milestone, no single subject
#   {dark,flat}_baseline   - capture-and-store; the trailing noun is the
#                            produced artifact, not the operation
CARVE_OUT_KINDS = frozenset(
    {
        "first_light",
        "dark_baseline",
        "flat_baseline",
    }
)


def _scenario_files() -> list[Path]:
    return sorted(
        p for p in tracked_test_files() if "scenarios" in p.parts and "integration" in p.parts
    )


def _register_procedure_kinds(tree: ast.AST) -> list[tuple[int, str]]:
    """(lineno, kind) for every ``RegisterProcedure(kind="<literal>")`` call.

    Non-literal kinds (variables, f-strings) cannot be checked statically
    and are skipped; scenario tests use string literals.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr
            if isinstance(func, ast.Attribute)
            else None
        )
        if name != "RegisterProcedure":
            continue
        kind_kw = next((kw for kw in node.keywords if kw.arg == "kind"), None)
        if kind_kw is None:
            continue
        if isinstance(kind_kw.value, ast.Constant) and isinstance(kind_kw.value.value, str):
            found.append((kind_kw.lineno, kind_kw.value.value))
    return found


def _conforms(kind: str) -> bool:
    if kind in CARVE_OUT_KINDS:
        return True
    return kind.split("_")[-1] in APPROVED_OPERATION_NOUNS


@pytest.mark.architecture
def test_scenario_procedure_kinds_follow_noun_last_convention() -> None:
    violations: list[str] = []
    seen: set[str] = set()
    for path in _scenario_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, kind in _register_procedure_kinds(tree):
            seen.add(kind)
            if not _conforms(kind):
                violations.append(f"  {path.name}:{lineno}: kind={kind!r}")

    assert seen, (
        "no RegisterProcedure(kind=...) literals found under "
        "tests/integration/scenarios/ -- scope regression?"
    )

    if violations:
        pytest.fail(
            "\n".join(
                [
                    "Procedure kind(s) violate the noun-LAST naming convention "
                    "(docs/architecture/modules/operation/index.md):",
                    *violations,
                    "",
                    "A kind reads <subject>_<operation-noun>, operation noun LAST "
                    "(never a leading imperative verb, e.g. set_energy -> energy_setting).",
                    "Fix by one of:",
                    "  - rename so the operation noun is last;",
                    "  - add a genuinely new operation noun to APPROVED_OPERATION_NOUNS here;",
                    "  - add a milestone / capture idiom to CARVE_OUT_KINDS with a rationale.",
                ]
            )
        )
