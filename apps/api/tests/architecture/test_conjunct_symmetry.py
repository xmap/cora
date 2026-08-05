"""Architecture fitness: every conjunct narrows every principal alike, or says why not.

`test_actor_kind_blindness.py` pins the DOOR: no gate branches on whether a
principal is a machine. This file pins the ENVELOPE: no conjunct quietly
narrows one kind of principal and not another.

The two are different claims and the first does not imply the second. A gate
that never reads a kind can still bind agents on eight axes and humans on two,
because the narrowing arrives through the instrument a principal holds rather
than through a branch on what they are. Every step of that drift is individually
legal under kind-blindness, individually documented, and the endpoint is a system
whose symmetry describes a doorway and nothing else.

## The rule this file enforces

An axis may be bound only from an instrument the facility actually issues. Where
a conjunct binds some principals and not others, the gap is not an oversight to
be reported after the fact: it is an entry that must name the gesture the
facility does not perform, and the trigger that would retire the entry.

So the discipline is not "every conjunct must be symmetric". It is:

    Every asymmetric conjunct is enumerated, with the missing gesture named
    and a trigger that would retire it. A carve-out that expires fails as a
    stale entry rather than rotting into permanent background.

## Why this ships while `Conjunct` has one member

The ledger is empty today and the tests below all pass trivially. That is the
point, and it is the same reason `Conjunct` itself was defined with a single
member: the cost of answering "which principals does this narrow?" is near zero
at the moment a conjunct is written and near total once twenty of them exist.
An empty ledger shipped now is a question the next author cannot route around.
A ledger written after the drift is an audit, and an audit is what this repo
already learned does not hold.

## What the ledger cannot do

It records a declaration, not a discovery. Unlike the kind-blindness sweep,
which reads branches out of the AST, nothing in the syntax of a conjunct reveals
which principals it narrows. Rule 4 exists because of that: the one live
classification is backed by a structural check rather than by its author's word,
and any future conjunct claiming `EVERY_PRINCIPAL` should earn a comparable
check rather than inheriting this one's credibility.
"""

import ast
from dataclasses import dataclass
from enum import StrEnum

import pytest

from cora.infrastructure.ports.authorize import Conjunct
from tests.architecture.conftest import CORA_ROOT


class _PrincipalReach(StrEnum):
    """Which principals a conjunct actually narrows."""

    EVERY_PRINCIPAL = "every_principal"
    SOME_PRINCIPALS = "some_principals"


@dataclass(frozen=True)
class _CarveOut:
    """Why a conjunct narrows some principals, and what would end that.

    Named for the RECORD, not for the condition. The asymmetry is already
    present in the code once a conjunct binds unevenly; what an author adds
    here is the excusing entry, and the sibling file uses the same word for
    the same job. `_Justification` is refused: `cora.shared.justification`
    owns that noun for the obligation gate, which calls itself the deontic
    dual of authorization, so the overload would land in the one place it is
    most expensive.

    `missing_gesture` is the load-bearing field and the one that makes this
    a derivation rule rather than a disclosure habit. An asymmetry is
    admissible when the facility performs a narrowing act for one kind of
    principal and no comparable act for another; it is NOT admissible merely
    because CORA finds one side easier to bind. Naming the absent gesture is
    what forces that distinction at write time, and it is frequently the
    point where the axis turns out to have been modelled wrong: an asymmetry
    with no nameable missing gesture is usually a conjunct keyed on the
    principal when it should have been keyed on the request.
    """

    narrowed_principals: str
    reason: str
    missing_gesture: str
    trigger: str


# Every member of `Conjunct`, classified. Asserted against the enum in BOTH
# directions, so a new conjunct fails as an unclassified addition and a removed
# one fails as a stale entry.
_REACH_LEDGER: dict[Conjunct, _PrincipalReach] = {
    Conjunct.POLICY: _PrincipalReach.EVERY_PRINCIPAL,
    # Reads `Actor.active`. Every principal HAS an Actor, agents included:
    # `define_agent` writes the agent's Actor at the same id in one
    # cross-BC transaction, so `Agent.id == Actor.id` and one field
    # describes both kinds. Not "symmetric because we were careful", but
    # symmetric because there is only one fact to read.
    Conjunct.LIVENESS: _PrincipalReach.EVERY_PRINCIPAL,
}

# Carve-outs for the conjuncts classified `SOME_PRINCIPALS`. Empty is the
# honest state today and the tests keep it honest in both directions: an
# asymmetric conjunct with no entry fails, and an entry for a conjunct that is
# no longer asymmetric fails as stale.
_CARVE_OUT_LEDGER: dict[Conjunct, _CarveOut] = {}

# Backs the sole `EVERY_PRINCIPAL` classification structurally rather than by
# assertion. `Policy` is the only aggregate the gate consults, and it can only
# narrow every principal alike if it holds nothing to tell them apart by.
_POLICY_STATE_PATH = CORA_ROOT / "trust" / "aggregates" / "policy" / "state.py"


def _policy_field_names() -> frozenset[str]:
    tree = ast.parse(_POLICY_STATE_PATH.read_text())
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Policy":
            return frozenset(
                member.target.id
                for member in node.body
                if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name)
            )
    raise AssertionError(f"{_POLICY_STATE_PATH.name} declares no `Policy` class")


@pytest.mark.architecture
def test_conjunct_absent_from_reach_ledger_is_rejected() -> None:
    unclassified = sorted(frozenset(Conjunct) - frozenset(_REACH_LEDGER))
    assert not unclassified, (
        "Conjunct member(s) with no entry in `_REACH_LEDGER`:\n  "
        + "\n  ".join(unclassified)
        + "\n\nA conjunct narrows the set of permitted requests, and the question this "
        "ledger exists to force is WHOSE requests. Classify it `EVERY_PRINCIPAL` if it "
        "narrows every principal alike, or `SOME_PRINCIPALS` plus an `_CARVE_OUT_LEDGER` "
        "entry naming the gesture the facility does not perform for the others. If that "
        "gesture is hard to name, the conjunct is probably keyed on the principal where "
        "it should be keyed on the request; that reframing is the usual fix and it is "
        "cheaper here than after the conjunct ships."
    )


@pytest.mark.architecture
def test_reach_ledger_entry_without_conjunct_is_rejected() -> None:
    stale = sorted(frozenset(_REACH_LEDGER) - frozenset(Conjunct))
    assert not stale, (
        "`_REACH_LEDGER` entr(ies) naming no live Conjunct member:\n  "
        + "\n  ".join(stale)
        + "\n\nThe conjunct was removed or renamed. Delete the entry so the ledger keeps "
        "reading as the true, complete classification rather than as accumulated history."
    )


@pytest.mark.architecture
def test_asymmetric_conjunct_without_a_carve_out_is_rejected() -> None:
    asymmetric = frozenset(
        conjunct
        for conjunct, reach in _REACH_LEDGER.items()
        if reach is _PrincipalReach.SOME_PRINCIPALS
    )
    uncarved = sorted(asymmetric - frozenset(_CARVE_OUT_LEDGER))
    assert not uncarved, (
        "Conjunct(s) classified SOME_PRINCIPALS with no `_CARVE_OUT_LEDGER` entry:\n  "
        + "\n  ".join(uncarved)
        + "\n\nAn asymmetry that is merely disclosed drifts; one that must name its own "
        "missing gesture and its own retirement trigger does not. Add a `_CarveOut` "
        "saying who the conjunct narrows, why that is acceptable meanwhile, which "
        "facility gesture is absent for everyone else, and what would retire the entry."
    )


@pytest.mark.architecture
def test_carve_out_without_asymmetric_conjunct_is_rejected() -> None:
    asymmetric = frozenset(
        conjunct
        for conjunct, reach in _REACH_LEDGER.items()
        if reach is _PrincipalReach.SOME_PRINCIPALS
    )
    stale = sorted(frozenset(_CARVE_OUT_LEDGER) - asymmetric)
    assert not stale, (
        "`_CARVE_OUT_LEDGER` entr(ies) for conjuncts that are not asymmetric:\n  "
        + "\n  ".join(stale)
        + "\n\nEither the conjunct now narrows every principal alike, in which case the "
        "entry is the record of a gap that closed and should be deleted, or it was "
        "removed entirely. A ledger that keeps closed entries stops reading as the list "
        "of live exceptions, which is the only thing it is for."
    )


@pytest.mark.architecture
def test_carve_out_with_an_unanswered_field_is_rejected() -> None:
    blank = sorted(
        f"{conjunct}.{field}"
        for conjunct, carve_out in _CARVE_OUT_LEDGER.items()
        for field, value in (
            ("narrowed_principals", carve_out.narrowed_principals),
            ("reason", carve_out.reason),
            ("missing_gesture", carve_out.missing_gesture),
            ("trigger", carve_out.trigger),
        )
        if not value.strip()
    )
    assert not blank, (
        "`_CARVE_OUT_LEDGER` field(s) left empty:\n  "
        + "\n  ".join(blank)
        + "\n\nEvery field is a question the rule refuses to let go unanswered. An empty "
        "`missing_gesture` in particular means nobody established that the facility "
        "narrows one principal and not another, which is the difference between an "
        "asymmetry the world imposes and one CORA invented."
    )


@pytest.mark.architecture
def test_policy_conjunct_holds_nothing_to_tell_principals_apart() -> None:
    kindish = sorted(
        field
        for field in _policy_field_names()
        if field == "kind" or field.endswith("_kind") or field.startswith("kind_")
    )
    assert not kindish, (
        "`Policy` gained a kind-shaped field:\n  "
        + "\n  ".join(kindish)
        + "\n\nThe Policy conjunct is classified EVERY_PRINCIPAL in `_REACH_LEDGER`, "
        "and that classification rests on Policy holding nothing it could tell two "
        "principals apart by: it carries a flat `permitted_principal_ids` set of bare "
        "identifiers and a flat `permitted_commands` set. A kind-shaped field would make "
        "the classification false while every test that reads it kept passing. Reclassify "
        "the conjunct before adding the field, not after."
    )
