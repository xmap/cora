"""Pin: every aggregate's genesis event class ends in `Defined` or `Registered`.

The CORA convention (see `project_defined_vs_registered_genesis.md`) splits
the genesis verb on the template-vs-instance axis:

  - `<Aggregate>Defined` for templates, contracts, blueprints, declarative
    artifacts (Family, Capability, Method, Plan, Practice, Recipe, Assembly,
    Agent, Calibration, Model, Permit, Conduit, Policy, Surface, Zone,
    ClearanceTemplate).

  - `<Aggregate>Registered` for instances, occurrences, identities, runtime
    bindings (Asset, Fixture, Frame, Mount, Procedure, Run, Visit, Subject,
    Actor, Caution, Campaign, Decision, Enclosure, Dataset, Credential,
    Facility, Supply, Clearance).

The template-vs-instance classification is semantic, not structural: the
directory name does not encode it (`equipment/family` and `equipment/asset`
sit in identical-shape directories). The only directory that bakes the
distinction into its name is `safety/clearance_template`, and that is the
exception, not the rule.

This fitness function therefore takes the cheap predicate: it asserts the
genesis class name ends in one of the two recognized suffixes, without
taking a position on which. That catches the high-risk drift of a future
author defaulting to `<Aggregate>Created` / `<Aggregate>Initialized` /
`<Aggregate>Opened`. A direction-enforcing companion (`Defined` iff
template, `Registered` iff instance) would require a hand-maintained
per-aggregate classification map; we defer it until a rule-of-three
misclassification fires.

## Genesis event identification

The genesis event is the FIRST member of the aggregate's
`<Aggregate>Event` discriminated union. Today every aggregate's
`events.py` declares exactly one such union, either as a PEP 604 pipe
chain (`A | B | C`) or as a single-class assignment (`<Aggregate>Event = A`).
Pipe chains are left-associative, so the leftmost name is the first
declared; the AST walker preserves that order.

## Documented deviations

Four aggregates do not match the rule. All are intentional and load-bearing:

  - `run/run` emits `RunStarted` at genesis. The Run aggregate collapses
    register + start into a single event; renaming to `RunRegistered`
    would lose the transition into the Running phase that the rest of
    the Run lifecycle depends on.

  - `federation/seal` emits `SealInitialized`. The Seal aggregate is the
    cryptographic chain-root for a Facility's append-only event stream;
    the verb encodes the chain-genesis semantic rather than the
    instance-registration framing.

  - `data/acquisition` emits `AcquisitionRecorded`. The Acquisition
    aggregate is a recorded-fact-chain (terminal at genesis); the verb
    encodes a stated fact at a moment rather than instance registration.

  - `data/attestation` emits `AttestationRecorded`. The Attestation
    aggregate is a terminal-at-genesis recorded-fact-chain; the verb
    encodes the recording of a verify/format/bit-rot fact rather than
    instance registration.

All deviations are pinned in `_GENESIS_VERB_DEVIATIONS` below. A
sibling test enforces that each allowlisted aggregate STILL has a
non-matching genesis (so that if a future refactor renames the genesis
event to `<Aggregate>Defined` or `<Aggregate>Registered`, the allowlist
entry is forced to be pruned rather than silently exempting a now-
compliant aggregate).
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

_GENESIS_SUFFIXES: frozenset[str] = frozenset({"Defined", "Registered"})


_GENESIS_VERB_DEVIATIONS: dict[tuple[str, str], str] = {
    ("run", "run"): (
        "RunStarted collapses register and start into a single genesis "
        "event. The Run lifecycle (Held, Resumed, Completed, Aborted, "
        "Truncated) depends on the transition into the Running phase "
        "that the genesis verb encodes; renaming to RunRegistered would "
        "lose that transition without removing a real ambiguity."
    ),
    ("federation", "seal"): (
        "SealInitialized reflects cryptographic-chain-root semantics. "
        "The Seal aggregate is the genesis of a per-Facility append-only "
        "event stream; the verb encodes chain-initialization rather than "
        "the instance-registration framing covered by the convention."
    ),
    ("data", "acquisition"): (
        "AcquisitionRecorded reflects recorded-fact-chain semantics: an "
        "Acquisition is the birth-certificate fact that a producing Asset "
        "captured bytes into a Dataset, terminal at genesis (one event "
        "ever per stream). The `record` verb encodes a stated fact at a "
        "moment, not an instance template or a runtime binding; renaming "
        "to AcquisitionRegistered would mislabel a fact as an instance."
    ),
    ("data", "attestation"): (
        "AttestationRecorded is a terminal-at-genesis recorded-fact-chain "
        "(one stream per Attestation; a single AttestationRecorded event). "
        "The verb encodes the recording of a verify/format/bit-rot fact, "
        "not the registration of a long-lived instance; renaming to "
        "AttestationRegistered would misframe a fact as an entity. Mirrors "
        "the Calibration-revision / run / seal fact-shaped precedent."
    ),
}


def _events_files() -> list[Path]:
    """Tracked `events.py` files under `cora/<bc>/aggregates/<aggregate>/`."""
    return sorted(
        path
        for path in tracked_python_files()
        if path.name == "events.py" and "/aggregates/" in str(path)
    )


def _aggregate_key(path: Path) -> tuple[str, str]:
    """Return `(bc, aggregate_dir)` for a `cora/<bc>/aggregates/<agg>/events.py` path."""
    rel = path.relative_to(CORA_ROOT).parts
    return rel[0], rel[2]


def _qualified(path: Path) -> str:
    return "cora." + ".".join(path.relative_to(CORA_ROOT).with_suffix("").parts)


def _flatten_union_in_order(node: ast.expr) -> Iterable[str]:
    """Yield names from a union expression in left-to-right declaration order.

    Handles three shapes:
      - PEP 604 pipe form: `A | B | C` (ast.BinOp with ast.BitOr op)
      - typing.Union subscript form: `Union[A, B, C]` (ast.Subscript with Tuple slice)
      - Bare single class: `Foo` (ast.Name)

    BinOp is left-associative under Python's parser, so `A | B | C` parses
    as `((A | B) | C)`; recursing left-first preserves declaration order.
    """
    if isinstance(node, ast.Name):
        yield node.id
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        yield from _flatten_union_in_order(node.left)
        yield from _flatten_union_in_order(node.right)
    elif isinstance(node, ast.Subscript):
        slice_node = node.slice
        if isinstance(slice_node, ast.Tuple):
            for elt in slice_node.elts:
                yield from _flatten_union_in_order(elt)
        else:
            yield from _flatten_union_in_order(slice_node)


def _genesis_event_class(tree: ast.AST) -> str | None:
    """Return the name of the FIRST event class in the `<Aggregate>Event` union.

    Walks top-level Assign / AnnAssign / TypeAlias for a target named ending
    in `Event` and returns the first union member. Returns None when no
    `<Aggregate>Event` assignment is present.
    """
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
            members = list(_flatten_union_in_order(value))
            return members[0] if members else None
    return None


def _ends_with_genesis_suffix(class_name: str) -> bool:
    return any(class_name.endswith(suffix) for suffix in _GENESIS_SUFFIXES)


@pytest.mark.architecture
@pytest.mark.parametrize("path", _events_files(), ids=_qualified)
def test_genesis_event_uses_defined_or_registered_suffix(path: Path) -> None:
    """Every aggregate's genesis event class name ends in `Defined` or
    `Registered`, unless the aggregate is explicitly allowlisted in
    `_GENESIS_VERB_DEVIATIONS`."""
    key = _aggregate_key(path)
    tree = ast.parse(path.read_text())
    genesis = _genesis_event_class(tree)
    if genesis is None:
        pytest.skip(f"{_qualified(path)} declares no <Aggregate>Event union")
    if key in _GENESIS_VERB_DEVIATIONS:
        return
    assert _ends_with_genesis_suffix(genesis), (
        f"{_qualified(path)}: genesis event class {genesis!r} does not end "
        f"in one of {sorted(_GENESIS_SUFFIXES)}.\n\n"
        "The CORA convention is that the FIRST member of the "
        "`<Aggregate>Event` union (the event that creates a new aggregate "
        "stream) ends in `Defined` (templates / contracts / blueprints) "
        "or `Registered` (instances / occurrences / runtime bindings). "
        "See `project_defined_vs_registered_genesis.md` for the rationale "
        "and the documented edge-case framings.\n\n"
        "If this aggregate genuinely deviates (a lifecycle verb like "
        "`Started` or a chain-genesis verb like `Initialized` carries "
        "load-bearing semantic the convention erases), add "
        f"{key!r} to `_GENESIS_VERB_DEVIATIONS` in this file with a "
        "rationale that names what the standard verbs would lose. "
        "Otherwise rename the genesis class to match the convention."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("key", sorted(_GENESIS_VERB_DEVIATIONS))
def test_deviation_allowlist_entries_still_deviate(key: tuple[str, str]) -> None:
    """Every allowlist entry MUST still have a genesis class that does NOT
    end in `Defined` or `Registered`. Catches stale entries whose genesis
    was renamed to match the convention during an unrelated refactor.
    """
    bc, aggregate_dir = key
    candidates = [path for path in _events_files() if _aggregate_key(path) == key]
    assert candidates, (
        f"Deviation allowlist entry {key!r} resolves to no tracked events.py; "
        f"expected cora/{bc}/aggregates/{aggregate_dir}/events.py. Either "
        "the aggregate was removed (prune the entry) or the directory was "
        "renamed (update the entry)."
    )
    assert len(candidates) == 1, (
        f"Deviation allowlist entry {key!r} resolves to multiple events.py "
        f"files: {[_qualified(p) for p in candidates]}"
    )
    tree = ast.parse(candidates[0].read_text())
    genesis = _genesis_event_class(tree)
    assert genesis is not None, (
        f"{_qualified(candidates[0])} declares no <Aggregate>Event union; "
        f"remove {key!r} from the deviation allowlist."
    )
    assert not _ends_with_genesis_suffix(genesis), (
        f"{_qualified(candidates[0])}: genesis event class {genesis!r} now "
        f"ends in one of {sorted(_GENESIS_SUFFIXES)}, so the aggregate "
        f"no longer deviates from the convention. Remove {key!r} from "
        "`_GENESIS_VERB_DEVIATIONS` in this file."
    )
