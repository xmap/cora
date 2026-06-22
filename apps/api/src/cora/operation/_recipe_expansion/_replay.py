"""Recipe-expansion replay helpers for the `conduct_procedure` handler.

Per [[project-run-procedure-replay-design]] the run-time replay path
locates the genesis `RecipeExpansionRecorded` provenance event in a
Procedure stream, extracts the pinned hash + bindings + port-version
tuple, then verifies a freshly-re-expanded `tuple[Step, ...]` matches
the recorded pins. This module collects the pure helpers; the handler
threads them after authz + Procedure load.

This is the FIRST handler-tier site in CORA that reads
`StoredEvent.payload` directly outside a projection. Per replay-design
§Locks the rule-of-three threshold gates promoting the helper to a
shared module: when a SECOND handler (any BC) needs payload-direct
access, hoist `find_recipe_expansion_record` to a generic
`cora.infrastructure.event_payload` helper. For comparison, projections
also read `.payload` but at projection-fold time, not at
handler-orchestration time. See replay-design Anti-hook 12.
"""

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.operation._recipe_expansion._expand import steps_to_wire
from cora.operation.aggregates.procedure import (
    RecipeExpansionRecordNotFoundError,
    RecipeExpansionReplayMismatchError,
)
from cora.operation.conductor import Step
from cora.shared.canonical_json import canonical_json_bytes


@dataclass(frozen=True)
class RecipeExpansionPins:
    """The replay-pinned subset of a `RecipeExpansionRecorded` payload.

    Constructed by `pins_from_payload`. Carries only the fields the
    replay path needs (control flow), NOT the audit-only fields
    (procedure_id, recipe_id, capability_id, capability_version,
    step_count, occurred_at) which are read directly at the handler
    entry for logging.
    """

    recipe_version: str | None
    bindings: Mapping[str, Any]
    bindings_hash: str
    steps_hash: str
    expansion_port_version: str


def find_recipe_expansion_record(
    stored_events: Iterable[StoredEvent],
) -> StoredEvent | None:
    """Locate the `RecipeExpansionRecorded` event in a Procedure stream.

    Scans linearly from head, returns the first match, early-exits on
    first hit. In well-formed Recipe-driven Procedure streams the match
    lands at index 1 (the second event in the genesis 2-event block
    emitted by `register_procedure_from_recipe`); the unit test pins
    this position invariant. Tail-scan is wrong: only the genesis
    `RecipeExpansionRecorded` defines the replay snapshot.

    Returns `None` when no match. The caller decides whether None is
    expected (legacy Procedure with `recipe_id is None`) or an error
    (recipe-driven Procedure missing its provenance event, raised as
    `RecipeExpansionRecordNotFoundError` by the handler).
    """
    for event in stored_events:
        if event.event_type == "RecipeExpansionRecorded":
            return event
    return None


_REQUIRED_PINS_KEYS = (
    "bindings",
    "bindings_hash",
    "expansion_port_version",
    "steps_hash",
)


def pins_from_payload(procedure_id: UUID, payload: Mapping[str, Any]) -> RecipeExpansionPins:
    """Extract the replay-pinned subset from a `RecipeExpansionRecorded` payload.

    Defensive: raises `RecipeExpansionRecordNotFoundError(procedure_id)`
    if any required key is missing (covers the corrupt-payload case
    distinct from missing-event case; both surface the same error
    family per the replay-design lock on triage simplicity).
    """
    missing = [key for key in _REQUIRED_PINS_KEYS if key not in payload]
    if missing:
        raise RecipeExpansionRecordNotFoundError(procedure_id)
    return RecipeExpansionPins(
        recipe_version=payload.get("recipe_version"),
        bindings=dict(payload["bindings"]),
        bindings_hash=payload["bindings_hash"],
        steps_hash=payload["steps_hash"],
        expansion_port_version=payload["expansion_port_version"],
    )


def verify_bindings_hash(procedure_id: UUID, pins: RecipeExpansionPins) -> None:
    """Verify the recorded `bindings` payload still hashes to `bindings_hash`.

    Raises `RecipeExpansionReplayMismatchError(procedure_id, "bindings")`
    on mismatch. Bindings drift is input drift (the recorded payload
    no longer canonicalizes to its recorded hash, i.e. payload
    corruption); failing it BEFORE the steps check isolates the failure
    mode in the discriminator value, easier to triage than a downstream
    steps mismatch caused by upstream binding corruption.
    """
    recomputed = hashlib.sha256(canonical_json_bytes(dict(pins.bindings))).hexdigest()
    if recomputed != pins.bindings_hash:
        raise RecipeExpansionReplayMismatchError(procedure_id, "bindings")


def verify_steps_hash(
    procedure_id: UUID,
    steps: tuple[Step, ...],
    pins: RecipeExpansionPins,
) -> None:
    """Verify the re-expanded steps still hash to the recorded `steps_hash`.

    Raises `RecipeExpansionReplayMismatchError(procedure_id, "steps")`
    on mismatch. Steps drift is expansion-logic drift (the port
    produces different output for the same input than at write time);
    runs AFTER `verify_bindings_hash` because steps drift downstream
    of bindings is a confusing diagnostic.
    """
    recomputed = hashlib.sha256(canonical_json_bytes(steps_to_wire(steps))).hexdigest()
    if recomputed != pins.steps_hash:
        raise RecipeExpansionReplayMismatchError(procedure_id, "steps")


MismatchField = Literal["bindings", "steps"]


__all__ = [
    "MismatchField",
    "RecipeExpansionPins",
    "find_recipe_expansion_record",
    "pins_from_payload",
    "verify_bindings_hash",
    "verify_steps_hash",
]
