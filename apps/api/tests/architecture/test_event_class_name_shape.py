"""Pin: every event class name contains at least one past-participle token.

Domain events name what HAPPENED, in past tense. Across the 16-BC
corpus the shape is `<Aggregate><PastParticiple>` (AssetRegistered,
VisitArrived, CautionSuperseded) with three sanctioned non-trivial
extensions:

  - Supply's operator-observation events embed the past participle
    in the middle: `SupplyMarkedAvailable`, `SupplyMarkedUnavailable`,
    `SupplyMarkedRecovering`. `Marked` is the past participle; the
    trailing status is the discriminator that distinguishes operator-
    audit from a future automated monitor.

  - Run's cross-aggregate edit events keep the past participle in the
    middle and carry a preposition + sibling aggregate at the end:
    `RunAddedToCampaign`, `RunRemovedFromCampaign`. The trailing token
    is a noun (the sibling aggregate), not a participle.

  - Visit's phrasal-verb transitions split the past participle from
    its preposition: `VisitCheckedIn`, `VisitCheckedOut`. The trailing
    token is a preposition.

The check is therefore "the name CONTAINS at least one past-participle
token", not "the name ENDS in a past-participle token". Past-participle
suffix allowlist: `-ed`, `-en`. The `-ld` suffix is NOT a catch-all
(too many non-participle English words end in `-ld`: Build, Field,
Shield, Yield, Guild, Child, Mold, Fold, Hold, Gold, Bold, Cold).
Irregular `-ld` participles (Held, Sold, Told) are listed individually
in `_IRREGULAR_PARTICIPLES` (currently only `Held`); extend that set
if a future event picks up a new irregular form.

Discriminator: event-class names come from each aggregate's
`<Aggregate>Event` discriminated union, not from every dataclass in
`events.py`. Value objects declared alongside events (for example
`CautionAcknowledgement` inside `run/aggregates/run/events.py`) are
deliberately excluded.
"""

import ast
import re
from collections.abc import Iterable
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

_PARTICIPLE_SUFFIXES: frozenset[str] = frozenset({"ed", "en"})
# `-ld` is NOT a participle suffix at the catch-all layer: too many
# non-participle English words end in `-ld` (Build, Field, Shield, Yield,
# Guild, Child, Mold, Fold, Hold, Gold, Bold, Cold). Past participles
# that genuinely end in `-ld` (Held, Sold, Told) are listed individually
# in `_IRREGULAR_PARTICIPLES`. Extend the allowlist when a future event
# legitimately picks up a new irregular form.
_IRREGULAR_PARTICIPLES: frozenset[str] = frozenset({"Bound", "Held", "Set", "Unbound", "Withdrawn"})

_TOKEN_RE = re.compile(r"[A-Z][a-z]*")


def _events_files() -> list[Path]:
    """Tracked `events.py` files under `cora/*/aggregates/*/`."""
    return sorted(
        path
        for path in tracked_python_files()
        if path.name == "events.py" and "/aggregates/" in str(path)
    )


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _is_participle_token(token: str) -> bool:
    """A token is a past-participle if it ends in one of the allowed suffixes
    or matches an irregular form by exact name."""
    if token in _IRREGULAR_PARTICIPLES:
        return True
    return any(token.endswith(suffix) for suffix in _PARTICIPLE_SUFFIXES)


def _contains_participle(name: str) -> bool:
    return any(_is_participle_token(t) for t in _TOKEN_RE.findall(name))


def _event_union_members(tree: ast.AST) -> set[str]:
    """Return event-class names appearing in any `<Aggregate>Event` union.

    Walks top-level Assign / AnnAssign / TypeAlias for a target named
    ending in `Event`. Two union syntaxes are recognized:

      - PEP 604 pipe form: `A | B | C` (ast.BinOp with ast.BitOr op)
      - typing.Union subscript form: `Union[A, B, C]` (ast.Subscript
        with Tuple or single Name slice)

    Returns empty when no Event union is present (an events.py without
    a discriminated union is itself a smell but a different fitness
    function's concern).
    """
    members: set[str] = set()

    def _flatten(node: ast.expr) -> Iterable[str]:
        if isinstance(node, ast.Name):
            yield node.id
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            yield from _flatten(node.left)
            yield from _flatten(node.right)
        elif isinstance(node, ast.Subscript):
            slice_node = node.slice
            if isinstance(slice_node, ast.Tuple):
                for elt in slice_node.elts:
                    yield from _flatten(elt)
            else:
                yield from _flatten(slice_node)

    for node in ast.iter_child_nodes(tree):
        target_name: str | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                target_name = target.id
                value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
            value = node.value
        elif isinstance(node, ast.TypeAlias):
            target_name = node.name.id
            value = node.value
        if target_name and target_name.endswith("Event") and value is not None:
            members.update(_flatten(value))
    return members


@pytest.mark.architecture
@pytest.mark.parametrize("path", _events_files(), ids=_qualified)
def test_event_class_names_contain_past_participle(path: Path) -> None:
    """Each name in the aggregate's Event union contains a past-participle token."""
    tree = ast.parse(path.read_text())
    members = _event_union_members(tree)
    if not members:
        pytest.skip(f"{_qualified(path)} declares no <Aggregate>Event union")
    offenders = sorted(name for name in members if not _contains_participle(name))
    assert not offenders, (
        f"{_qualified(path)} declares event class(es) without a past-participle token:\n  "
        + "\n  ".join(offenders)
        + "\n\nEvery domain event must encode WHAT HAPPENED in past tense. The check is "
        "structural: split the class name into CamelCase tokens and assert at least one "
        "ends in -ed / -en, or is an irregular past participle. If the event truly "
        "needs a non-participle form (a new operator-observation pattern beyond Supply's "
        "Marked<Status>, for example), extend `_IRREGULAR_PARTICIPLES` or document the new "
        "carve-out alongside it."
    )
