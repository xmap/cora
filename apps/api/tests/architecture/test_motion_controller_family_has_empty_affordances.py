"""Pin the empty-Affordances leaf-Family convention for MotionController.

Per [[project_controller_as_asset_stage1_design]] (locked 2026-06-08
across six commits), Families with empty Affordances are operational
leaves in the drive-electronics composition chain. Their Assets are
registered honestly (so operators can see firmware versions and target
Cautions at the actual hardware) but stay in `AssetLifecycle.Commissioned`
indefinitely because there is no command surface for `Active` to mean
anything; activation ceremonies live at the parent stage Asset, not at
the controller. `MotionController` is the first such leaf Family.

This fitness pins the upstream invariant: every `DefineFamily` call
naming a leaf Family MUST pass `affordances=frozenset()` (empty). If
a future contributor amends `MotionController` to carry Affordances,
the convention has shifted; the contributor is asked to either revert
or update the design memo + this fitness together. The downstream
activation convention (operators do not call `activate_asset` on
controller Assets) is operator discipline, not kernel-enforced; this
fitness is the cheap floor that catches the foundational shape drift,
not the full runtime invariant. The full runtime check belongs in a
conftest-style event-store interceptor that lands when the trigger
fires (an actual controller activation attempt).

Future leaves (e.g. `TimingController`, `Lantronix XPort`) extend this
fitness by adding their Family name to `_LEAF_FAMILIES` (the compute
node host already landed as `ComputeNode`). Per the design memo's
anti-hook, each new addition needs its own intentional-design call
confirming the leaf shape fits.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import tracked_python_files, tracked_test_files

# ComputeNode (project-compute-modeling-stage0-design L8):
# the compute-hardware box that a reconstruction Plan binds. An empty-
# affordance leaf like MotionController, it carries GPU/RAM in its
# settings_schema and is never activated (define_plan / start_run gate
# only on Decommissioned, so a Commissioned compute node binds + runs
# without an activation ceremony). Its intentional-design call: a compute
# node has no device-affordance command surface; usage in a recon Plan is
# the hardware-identity fact that earns the Asset.
_LEAF_FAMILIES: frozenset[str] = frozenset({"MotionController", "ComputeNode"})


def _scan_define_family_calls(path: Path) -> list[tuple[int, str, ast.expr | None]]:
    """Return `(line, family_name, affordances_node)` for every
    `DefineFamily(name=<literal>, affordances=<node>)` call site.

    Skips call sites whose `name` argument is not a string literal
    (e.g. forwarded from a body / kw expression); those cannot be
    statically classified as leaf vs non-leaf and the runtime check
    is the right home for them.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    hits: list[tuple[int, str, ast.expr | None]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Name) and func.id == "DefineFamily") or (
            isinstance(func, ast.Attribute) and func.attr == "DefineFamily"
        ):
            pass
        else:
            continue
        name_value: str | None = None
        affordances_value: ast.expr | None = None
        for kw in node.keywords:
            if (
                kw.arg == "name"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                name_value = kw.value.value
            elif kw.arg == "affordances":
                affordances_value = kw.value
        if name_value is None:
            continue
        hits.append((node.lineno, name_value, affordances_value))
    return hits


def _is_empty_frozenset(node: ast.expr) -> bool:
    """True if `node` is the literal `frozenset()` call with no args."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id == "frozenset":
        return not node.args and not node.keywords
    return False


@pytest.mark.architecture
def test_leaf_families_define_empty_affordances() -> None:
    """Every `DefineFamily(name=<leaf>, ...)` site uses `affordances=frozenset()`.

    Catches the regression where a future contributor adds Affordances
    to `MotionController` (or any other leaf Family in `_LEAF_FAMILIES`)
    without updating the leaf convention. The downstream activation
    rule rests on this upstream shape: an Asset added only to empty-
    Affordances Families has no command surface for `Active` to mean
    anything.
    """
    paths = tracked_python_files() | tracked_test_files()
    violations: list[str] = []
    for path in paths:
        for line, family_name, affordances in _scan_define_family_calls(path):
            if family_name not in _LEAF_FAMILIES:
                continue
            if affordances is None or not _is_empty_frozenset(affordances):
                violations.append(
                    f'  {path}:{line}: DefineFamily(name="{family_name}", ...) '
                    f"has non-empty (or non-literal) affordances"
                )
    assert violations == [], (
        f"Leaf-Family convention violated: {len(violations)} site(s) define a leaf "
        f"Family with non-empty affordances. Leaf Families ({sorted(_LEAF_FAMILIES)}) "
        f"terminate at AssetLifecycle.Commissioned because they have no command "
        f"surface for Active to mean anything; activation ceremonies live at the "
        f"parent stage Asset. Either revert the affordances change, or update the "
        f"convention + this fitness + project_controller_as_asset_stage1_design "
        f"together.\n" + "\n".join(violations)
    )
