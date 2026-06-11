"""Pin: every transversal-time fold on aggregate state pairs with a
matching transversal-attribution fold on the same dataclass, and vice
versa. ERROR mode, CI-blocking, no asymmetric-fold allowlist; the only
exemption channel is the closed intrinsic-data list.

The "every fact has an actor" rule (see [[project-axes-foundation]] and
[[project-fold-symmetry-design]]) requires that any aggregate fold of
WHEN a fact-act happened lands together with a fold of WHO performed
the act, on the same dataclass and under canonical past-participle
naming. The fitness test runs two AST passes over every aggregate
state.py + events.py under `apps/api/src/cora/**/aggregates/**/`.

Pass 1 (state-side symmetry):

  - Every frozen dataclass under an aggregate state.py module.
  - TIME field = annotation contains `datetime` (incl. `datetime | None`).
  - ATTRIBUTION field = annotation is `ActorId` or `ActorId | None`
    (NewType-based; bare UUID is NOT flagged because cross-aggregate
    refs carry their own NewType per [[project-fold-symmetry-design]]).
  - Pairing predicate: strip `_at` / `_by` suffix to get the verb-stem;
    the same stem MUST appear in both halves on the same dataclass.
  - Dict-keyed VO special case: `dict[UUID, X]` AND value type X has a
    `<stem>_at` field -> dict KEY is the implicit `<stem>_by`; the
    `<stem>_at` on X is accepted as symmetric. Applies to
    `Decision.ratings: dict[UUID, DecisionRatingRecord]` where
    `DecisionRatingRecord.rated_at` is paired with the dict KEY.
  - Hard failure: any state field name ending in `_actor_id` post-rename.

Pass 2 (event-payload cross-check):

  - Three aggregates stay fold-NEITHER on state but their events MUST
    carry attribution: `data.Dataset`, `subject.Subject`, `supply.Supply`.
  - For Dataset / Subject: every event class with `occurred_at` MUST
    carry `<verb>_by: ActorId` where `<verb>` derives from the event
    class name (e.g. SubjectRegistered -> registered_by).
  - For Supply: every event class with `occurred_at` MUST carry
    `triggered_by` (trigger-aware discriminated union per Supply BC).

Allowlists are closed and carry inline justifications. New allowlist
entries require an explicit design-memo update.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


# ---------------------------------------------------------------------------
# Allowlists
# ---------------------------------------------------------------------------

# Intrinsic-data allowlist: fields that look like TIME or ATTRIBUTION
# under the syntactic predicate but are load-bearing intrinsic-data
# (calendar windows, schedule data, identity refs to non-Actor entities,
# successor pointers, authz allow-lists). Each entry carries a one-line
# justification matching the format
# `<bc>.<aggregate>[.<vo>].<field> -- <reason>`.
#
# Key format: "<bc>.<class>.<field>" or "<bc>.<class>.<vo>.<field>".
# `<class>` is the dataclass name as it appears in source, NOT the
# aggregate directory; nested VOs use their own class name.
_INTRINSIC_ALLOWLIST: dict[str, str] = {
    "caution.Caution.expires_at": "operator-supplied calendar deadline; not a fact-act",
    "caution.Caution.authored_by": (
        "genesis author identity-ref inherited through supersede / retire; "
        "the act-of-authoring is the genesis fold-NEITHER posture"
    ),
    "federation.Credential.expires_at": "contractual upper bound; not a fact-act",
    "federation.Permit.expires_at": "contractual upper bound; not a fact-act",
    "safety.Clearance.valid_from": "calendar window start; not a fact-act",
    "safety.Clearance.valid_until": "calendar window end; not a fact-act",
    "safety.Clearance.next_review_due_at": "scheduled review date; not a fact-act",
    "trust.Visit.planned_start_at": "operator-supplied planned window; not a fact-act",
    "trust.Visit.planned_end_at": "operator-supplied planned window; not a fact-act",
    "campaign.Campaign.lead_actor_id": (
        "long-haul PI ownership; not a fact-act fold. The name ends in "
        "`_actor_id` which Pass 1 otherwise bans post-rename, so the "
        "allowlist entry is the only escape hatch"
    ),
    "trust.Visit.PresenceEntry.check_in_at": (
        "implicit attribution via bare `actor_id` on the same VO "
        "(subject-of-presence coincident with check-in authority)"
    ),
    "trust.Visit.PresenceEntry.check_out_at": (
        "implicit attribution via bare `actor_id` on the same VO "
        "(subject-of-presence coincident with check-out authority)"
    ),
    "calibration.Calibration.AssertedSource.asserted_by": (
        "provenance-source identity-ref (vendor datasheet operator); "
        "contrast with fact-act-authority `CalibrationRevision.established_by`"
    ),
    "data.Acquisition.captured_at": (
        "caller-asserted instrument wall-clock (PROV-O generatedAtTime); "
        "the physical capturing entity is the `producing_asset_id` device, "
        "not an Actor, so there is no `captured_by` fact-act partner. The "
        "CORA-side recording act folds as the proper `recorded_at` / "
        "`recorded_by` pair on the same dataclass"
    ),
    "data.Edition.Creator.actor_id": (
        "publication-author identity-ref (credited creator on the citable Edition); "
        "ordered tuple semantics, NOT a fact-act fold"
    ),
}

# Aggregates whose events MUST carry the attribution half even though
# the aggregate state itself stays fold-NEITHER. Pass 2 enforces this.
# Key: "<bc>.<aggregate-dir>"; value: required field-name shape.
#   - "by"          -> event class FooedHappened MUST carry `<verb>_by: ActorId`
#                       where <verb> derives from the event class name.
#   - "triggered_by"-> event class MUST carry a bare `triggered_by` field
#                       (Supply's TriggerSource discriminated union).
_EVENTS_MUST_CARRY_ATTRIBUTION: dict[str, str] = {
    "data.dataset": "by",
    "subject.subject": "by",
    "supply.supply": "triggered_by",
}


# ---------------------------------------------------------------------------
# Shared AST helpers
# ---------------------------------------------------------------------------


_AGGREGATE_PATH_PATTERN = re.compile(
    r"/(?P<bc>[a-z_][a-z0-9_]*)/aggregates/(?P<aggregate>[a-z_][a-z0-9_]*)/state\.py$"
)
_EVENTS_PATH_PATTERN = re.compile(
    r"/(?P<bc>[a-z_][a-z0-9_]*)/aggregates/(?P<aggregate>[a-z_][a-z0-9_]*)/events\.py$"
)


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _bc_and_aggregate_for_state(path: Path) -> tuple[str, str] | None:
    match = _AGGREGATE_PATH_PATTERN.search(str(path))
    return (match.group("bc"), match.group("aggregate")) if match else None


def _bc_and_aggregate_for_events(path: Path) -> tuple[str, str] | None:
    match = _EVENTS_PATH_PATTERN.search(str(path))
    return (match.group("bc"), match.group("aggregate")) if match else None


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


# ---------------------------------------------------------------------------
# Annotation classification helpers
# ---------------------------------------------------------------------------


def _annotation_contains_name(annotation: ast.expr | None, target: str) -> bool:
    """True iff the annotation AST contains an identifier named `target`
    anywhere (handles `T`, `T | None`, `Optional[T]`, parametrized
    generics, etc.)."""
    if annotation is None:
        return False
    return any(isinstance(node, ast.Name) and node.id == target for node in ast.walk(annotation))


def _is_time_annotation(annotation: ast.expr | None) -> bool:
    return _annotation_contains_name(annotation, "datetime")


def _is_attribution_annotation(annotation: ast.expr | None) -> bool:
    """True iff the annotation is `ActorId` or `ActorId | None` (NewType-
    based attribution). Cross-aggregate identity refs carry their own
    NewType and are NOT flagged."""
    return _annotation_contains_name(annotation, "ActorId")


def _annotation_simple_name(annotation: ast.expr | None) -> str | None:
    """Best-effort extraction of a class-name from an annotation
    (handles bare `Name` and `Name | None` shapes)."""
    if annotation is None:
        return None
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        for side in (annotation.left, annotation.right):
            if isinstance(side, ast.Constant) and side.value is None:
                continue
            if isinstance(side, ast.Name):
                return side.id
    return None


def _is_dict_uuid_value(annotation: ast.expr | None) -> ast.expr | None:
    """For `dict[UUID, V]` shape, return the V annotation; else None."""
    if annotation is None or not isinstance(annotation, ast.Subscript):
        return None
    base = annotation.value
    base_name = (
        base.id
        if isinstance(base, ast.Name)
        else base.attr
        if isinstance(base, ast.Attribute)
        else None
    )
    if base_name != "dict":
        return None
    slice_node = annotation.slice
    if not isinstance(slice_node, ast.Tuple) or len(slice_node.elts) != 2:
        return None
    key, value = slice_node.elts
    if isinstance(key, ast.Name) and key.id == "UUID":
        return value
    return None


# ---------------------------------------------------------------------------
# Field stem extraction
# ---------------------------------------------------------------------------


def _verb_stem(field_name: str) -> str | None:
    """Strip the canonical `_at` / `_by` suffix; None if neither matches."""
    if field_name.endswith("_at"):
        return field_name[: -len("_at")]
    if field_name.endswith("_by"):
        return field_name[: -len("_by")]
    return None


def _class_field_annotations(class_def: ast.ClassDef) -> list[tuple[int, str, ast.expr]]:
    """Return (lineno, name, annotation) for every annotated assignment in
    the class body."""
    out: list[tuple[int, str, ast.expr]] = []
    for node in class_def.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.append((node.lineno, node.target.id, node.annotation))
    return out


# ---------------------------------------------------------------------------
# Allowlist helpers
# ---------------------------------------------------------------------------


def _intrinsic_keys_for_field(bc: str, class_name: str, field_name: str) -> tuple[str, ...]:
    """Possible allowlist keys for a field; checked in order."""
    return (f"{bc}.{class_name}.{field_name}",)


def _intrinsic_keys_for_nested(
    bc: str, root_class: str, vo_class: str, field_name: str
) -> tuple[str, ...]:
    """Possible allowlist keys for a nested-VO field; checked in order."""
    return (
        f"{bc}.{root_class}.{vo_class}.{field_name}",
        f"{bc}.{vo_class}.{field_name}",
    )


def _is_intrinsic(*keys: str) -> bool:
    return any(k in _INTRINSIC_ALLOWLIST for k in keys)


# ---------------------------------------------------------------------------
# File enumeration
# ---------------------------------------------------------------------------


def _aggregate_state_files() -> list[Path]:
    return sorted(
        path for path in tracked_python_files() if _bc_and_aggregate_for_state(path) is not None
    )


def _aggregate_event_files() -> list[Path]:
    return sorted(
        path for path in tracked_python_files() if _bc_and_aggregate_for_events(path) is not None
    )


# ---------------------------------------------------------------------------
# Pass 1: state-side symmetry check
# ---------------------------------------------------------------------------


def _root_aggregate_class_name(path: Path, tree: ast.AST) -> str | None:
    """Best-effort: the root aggregate class is typically named in
    PascalCase matching the aggregate directory. Falls back to the
    last frozen-dataclass in the module if no match found."""
    aggregate_dir = _bc_and_aggregate_for_state(path)
    if aggregate_dir is None:
        return None
    expected = "".join(part.capitalize() for part in aggregate_dir[1].split("_"))
    for cls in _frozen_dataclasses(tree):
        if cls.name == expected:
            return cls.name
    return None


def _collect_dict_uuid_value_class_names(tree: ast.AST) -> frozenset[str]:
    """Return the set of class names that appear as the VALUE type of a
    `dict[UUID, V]` field on any frozen dataclass in this tree. Those
    classes' `<stem>_at` fields are accepted as symmetric under the
    dict-keyed special case."""
    value_classes: set[str] = set()
    for cls in _frozen_dataclasses(tree):
        for _, _, annotation in _class_field_annotations(cls):
            value_annotation = _is_dict_uuid_value(annotation)
            if value_annotation is None:
                continue
            value_name = _annotation_simple_name(value_annotation)
            if value_name is not None:
                value_classes.add(value_name)
    return frozenset(value_classes)


@pytest.mark.architecture
@pytest.mark.parametrize("path", _aggregate_state_files(), ids=_qualified)
def test_state_side_fold_symmetry(path: Path) -> None:
    """Pass 1: every TIME field on aggregate state pairs with a matching
    ATTRIBUTION field on the same dataclass, and vice versa."""
    bc_and_agg = _bc_and_aggregate_for_state(path)
    assert bc_and_agg is not None  # guaranteed by _aggregate_state_files filter
    bc, _aggregate_dir = bc_and_agg

    tree = ast.parse(path.read_text())
    root_class = _root_aggregate_class_name(path, tree)
    dict_uuid_value_classes = _collect_dict_uuid_value_class_names(tree)

    offenders: list[str] = []
    for cls in _frozen_dataclasses(tree):
        fields = _class_field_annotations(cls)
        field_names = {name for _, name, _ in fields}

        # Hard failure: any field ending in `_actor_id` post-rename.
        for lineno, name, _ in fields:
            if name.endswith("_actor_id"):
                key = f"{bc}.{cls.name}.{name}"
                if key in _INTRINSIC_ALLOWLIST:
                    continue
                offenders.append(
                    f"line {lineno}: {cls.name}.{name} ends in `_actor_id` "
                    "(banned post-rename; strip to `<verb>_by`)"
                )

        # Treat this dataclass as a dict-keyed VO if its class name is
        # used as the value of a `dict[UUID, V]` field somewhere in this
        # module (typically on the aggregate root).
        is_dict_keyed_vo = cls.name in dict_uuid_value_classes

        for lineno, name, annotation in fields:
            # Skip `_actor_id`-suffixed fields; flagged separately above.
            if name.endswith("_actor_id"):
                continue

            time_field = _is_time_annotation(annotation)
            attribution_field = _is_attribution_annotation(annotation)

            if not (time_field or attribution_field):
                continue

            # Build allowlist keys to check.
            allowlist_keys: list[str] = list(_intrinsic_keys_for_field(bc, cls.name, name))
            if root_class is not None and cls.name != root_class:
                allowlist_keys.extend(_intrinsic_keys_for_nested(bc, root_class, cls.name, name))
            if _is_intrinsic(*allowlist_keys):
                continue

            stem = _verb_stem(name)
            if stem is None:
                # Field is typed as TIME or ATTRIBUTION but does not match
                # the canonical `<verb>_at` / `<verb>_by` shape.
                offenders.append(
                    f"line {lineno}: {cls.name}.{name} has TIME/ATTRIBUTION "
                    "type but does not match `<past-participle verb>_at|_by` "
                    "shape (or add to intrinsic-data allowlist)"
                )
                continue

            if time_field:
                expected_partner = f"{stem}_by"
                if expected_partner in field_names:
                    continue
                # Dict-keyed VO special case: the parent dict's KEY is
                # the implicit attribution. Accept the `_at` half as
                # symmetric.
                if is_dict_keyed_vo:
                    continue
                offenders.append(
                    f"line {lineno}: {cls.name}.{name} (TIME) has no paired "
                    f"`{expected_partner}` (ATTRIBUTION) on the same dataclass"
                )
            elif attribution_field:
                expected_partner = f"{stem}_at"
                if expected_partner in field_names:
                    continue
                offenders.append(
                    f"line {lineno}: {cls.name}.{name} (ATTRIBUTION) has no "
                    f"paired `{expected_partner}` (TIME) on the same dataclass"
                )

    assert not offenders, (
        f"{_qualified(path)} violates the fold-symmetry rule:\n  "
        + "\n  ".join(offenders)
        + "\n\nEvery transversal-time fold on aggregate state MUST pair "
        "with a matching transversal-attribution fold on the same "
        "dataclass under canonical `<past-participle verb>_at|_by` "
        "naming, and vice versa. See `project_fold_symmetry_design.md` "
        "for the rule, the intrinsic-data allowlist, and the dict-keyed "
        "VO special case."
    )


# ---------------------------------------------------------------------------
# Pass 2: event-payload cross-check
# ---------------------------------------------------------------------------


_CAMEL_SPLIT = re.compile(r"(?<!^)(?=[A-Z])")


def _event_verb_from_class_name(event_class: str, aggregate_pascal: str) -> str | None:
    """Derive the past-participle verb stem from an event class name.

    Strips the leading aggregate-PascalCase prefix when present (so
    `SubjectRegistered` -> `registered`); falls back to the last
    PascalCase token if no prefix match.
    """
    if event_class.startswith(aggregate_pascal):
        rest = event_class[len(aggregate_pascal) :]
    else:
        rest = event_class
    if not rest:
        return None
    # snake_case the remainder; multi-token tails (e.g. `MarkedAvailable`)
    # are joined with underscores so the verb stem matches the field name
    # convention.
    tokens = _CAMEL_SPLIT.split(rest)
    return "_".join(t.lower() for t in tokens if t)


def _aggregate_pascal(aggregate_dir: str) -> str:
    return "".join(part.capitalize() for part in aggregate_dir.split("_"))


def _events_in_module(tree: ast.AST) -> list[ast.ClassDef]:
    return _frozen_dataclasses(tree)


@pytest.mark.architecture
@pytest.mark.parametrize("path", _aggregate_event_files(), ids=_qualified)
def test_event_payload_attribution_required_for_fold_neither_aggregates(
    path: Path,
) -> None:
    """Pass 2: fold-NEITHER aggregates whose event payloads MUST carry
    attribution (Subject, Dataset, Supply) every event class with
    `occurred_at` carries the required attribution field."""
    bc_and_agg = _bc_and_aggregate_for_events(path)
    assert bc_and_agg is not None
    bc, aggregate_dir = bc_and_agg
    key = f"{bc}.{aggregate_dir}"
    required_shape = _EVENTS_MUST_CARRY_ATTRIBUTION.get(key)
    if required_shape is None:
        # No Pass 2 obligation for this aggregate; Pass 1 handles state.
        return

    aggregate_pascal = _aggregate_pascal(aggregate_dir)
    tree = ast.parse(path.read_text())

    offenders: list[str] = []
    for cls in _events_in_module(tree):
        fields = _class_field_annotations(cls)
        field_names_with_lines = {name: lineno for lineno, name, _ in fields}
        if "occurred_at" not in field_names_with_lines:
            continue

        if required_shape == "triggered_by":
            if "triggered_by" not in field_names_with_lines:
                offenders.append(
                    f"line {cls.lineno}: {cls.name} carries `occurred_at` "
                    "but is missing `triggered_by` (Supply trigger-aware "
                    "discriminated union)"
                )
            continue

        # required_shape == "by": derive `<verb>_by` from class name.
        verb = _event_verb_from_class_name(cls.name, aggregate_pascal)
        if verb is None:
            offenders.append(
                f"line {cls.lineno}: {cls.name} carries `occurred_at` but the "
                f"verb stem could not be derived from the class name "
                f"(expected `{aggregate_pascal}<Verb>`)"
            )
            continue
        expected_field = f"{verb}_by"
        if expected_field not in field_names_with_lines:
            offenders.append(
                f"line {cls.lineno}: {cls.name} carries `occurred_at` but is "
                f"missing `{expected_field}: ActorId` payload field"
            )

    assert not offenders, (
        f"{_qualified(path)} violates the fold-NEITHER-events-must-carry-"
        f"attribution rule:\n  "
        + "\n  ".join(offenders)
        + f"\n\n{key} stays fold-NEITHER on aggregate state but every "
        "event class with `occurred_at` MUST carry the matching "
        "attribution payload field. See `project_fold_symmetry_design.md` "
        "and the `_EVENTS_MUST_CARRY_ATTRIBUTION` table at the top of "
        "this file for the load-bearing fold-NEITHER aggregates."
    )


# ---------------------------------------------------------------------------
# Allowlist hygiene
# ---------------------------------------------------------------------------


def _intrinsic_entries() -> Iterable[tuple[str, str]]:
    return sorted(_INTRINSIC_ALLOWLIST.items())


@pytest.mark.architecture
@pytest.mark.parametrize(
    ("entry", "reason"),
    list(_intrinsic_entries()),
    ids=[e for e, _ in _intrinsic_entries()],
)
def test_intrinsic_allowlist_entry_carries_justification(entry: str, reason: str) -> None:
    """Every intrinsic-data allowlist entry carries a non-empty
    justification (catches accidental empty-string entries)."""
    assert reason.strip(), (
        f"intrinsic-data allowlist entry {entry!r} has an empty "
        "justification; add a one-line reason"
    )


def _locate_intrinsic_field(key: str) -> tuple[Path, ast.AnnAssign] | None:
    """Locate the AnnAssign node for a `<bc>.<class>[.<vo>].<field>` key.

    Walks `cora/<bc>/aggregates/**/state.py` and returns the first
    matching `(path, AnnAssign)` if found. Returns None if no
    aggregate state.py defines the named class with the named field.
    events.py files are intentionally not searched; Pass 1 only walks
    state.py, so an intrinsic allowlist entry pointing at an event
    payload field exempts nothing and should be removed.
    """
    parts = key.split(".")
    bc = parts[0]
    field = parts[-1]
    target_class = parts[-2]
    agg_dir = CORA_ROOT / bc / "aggregates"
    if not agg_dir.is_dir():
        return None
    for state in agg_dir.rglob("state.py"):
        tree = ast.parse(state.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name != target_class:
                continue
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Name)
                    and stmt.target.id == field
                ):
                    return (state, stmt)
    return None


@pytest.mark.architecture
@pytest.mark.parametrize("entry", sorted(_INTRINSIC_ALLOWLIST.keys()))
def test_intrinsic_allowlist_entry_actually_triggers_predicate(entry: str) -> None:
    """Every intrinsic-data allowlist entry MUST trip at least one Pass 1 check.

    The three Pass 1 checks an entry can trip:

    - the TIME predicate (annotation contains `datetime`),
    - the ATTRIBUTION predicate (annotation contains `ActorId`), or
    - the hard `_actor_id` rename-ban (field name ends in `_actor_id`).

    Catches defensive entries for fields that match none of the above
    (e.g. a `UUID`-typed field whose name doesn't end in `_actor_id`)
    which the allowlist exempts from nothing.
    """
    located = _locate_intrinsic_field(entry)
    assert located is not None, (
        f"intrinsic-data allowlist entry {entry!r} does not match any "
        "field on an aggregate state.py; remove the stale entry "
        "(event-payload fields belong to Pass 2, not the intrinsic allowlist)"
    )
    _, ann_node = located
    field_name = entry.rsplit(".", 1)[-1]
    triggers = (
        _is_time_annotation(ann_node.annotation)
        or _is_attribution_annotation(ann_node.annotation)
        or field_name.endswith("_actor_id")
    )
    assert triggers, (
        f"intrinsic-data allowlist entry {entry!r} has annotation "
        f"{ast.unparse(ann_node.annotation)!r} and field-name "
        f"{field_name!r}, which trip none of Pass 1's checks (TIME / "
        "ATTRIBUTION / `_actor_id` rename ban). The allowlist exempts "
        "nothing for this field; remove the entry."
    )
