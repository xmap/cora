"""Unit tests for the `_recipe_expansion` replay helpers.

Per [[project-run-procedure-replay-design]] §Operation BC seam
additions. The helpers locate the genesis `RecipeExpansionRecorded`
event in a Procedure stream, extract the pinned hash+bindings tuple,
and verify a freshly re-expanded `tuple[Step, ...]` matches the pins.
"""

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.operation._recipe_expansion import (
    RecipeExpansionPins,
    find_recipe_expansion_record,
    pins_from_payload,
    steps_to_wire,
    verify_bindings_hash,
    verify_steps_hash,
)
from cora.operation.aggregates.procedure import (
    RecipeExpansionRecordNotFoundError,
    RecipeExpansionReplayMismatchError,
)
from cora.operation.conductor import SetpointStep
from cora.shared.canonical_json import canonical_json_bytes

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-000000000099")


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Procedure",
        stream_id=_PROCEDURE_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


def _pins(bindings: dict[str, object] | None = None) -> RecipeExpansionPins:
    binds: dict[str, object] = bindings if bindings is not None else {"a": 1.0}
    bindings_hash = hashlib.sha256(canonical_json_bytes(dict(binds))).hexdigest()
    steps_hash = hashlib.sha256(
        canonical_json_bytes(steps_to_wire((SetpointStep(address="dev:x", value=1.0),)))
    ).hexdigest()
    return RecipeExpansionPins(
        recipe_version="v1",
        bindings=binds,
        bindings_hash=bindings_hash,
        steps_hash=steps_hash,
        expansion_port_version="v1",
    )


@pytest.mark.unit
def test_find_recipe_expansion_record_in_well_formed_stream_lands_at_index_one() -> None:
    """In well-formed Recipe-driven streams emitted by
    register_procedure_from_recipe, the match is the SECOND event
    (index 1) of the 2-event genesis block."""
    stream = [
        _stored("ProcedureRegistered", {}),
        _stored("RecipeExpansionRecorded", {"hint": "match"}),
        _stored("ProcedureStarted", {}),
    ]
    match = find_recipe_expansion_record(stream)
    assert match is not None
    assert match is stream[1]


@pytest.mark.unit
def test_find_recipe_expansion_record_with_two_matches_returns_first_match() -> None:
    stream = [
        _stored("ProcedureRegistered", {}),
        _stored("RecipeExpansionRecorded", {"hint": "first"}),
        _stored("RecipeExpansionRecorded", {"hint": "second"}),
    ]
    match = find_recipe_expansion_record(stream)
    assert match is not None
    assert match.payload == {"hint": "first"}


@pytest.mark.unit
def test_find_recipe_expansion_record_with_first_match_does_not_scan_subsequent_events() -> None:
    """Early-exit: a generator that raises if consumed past the first
    match confirms the helper stops scanning."""

    def _generator() -> Iterator[StoredEvent]:
        yield _stored("ProcedureRegistered", {})
        yield _stored("RecipeExpansionRecorded", {"hint": "match"})
        raise AssertionError("scanner consumed past first match")

    match = find_recipe_expansion_record(_generator())
    assert match is not None
    assert match.event_type == "RecipeExpansionRecorded"


@pytest.mark.unit
def test_find_recipe_expansion_record_with_no_match_returns_none() -> None:
    stream = [_stored("ProcedureRegistered", {}), _stored("ProcedureStarted", {})]
    assert find_recipe_expansion_record(stream) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "missing_key",
    ["bindings", "bindings_hash", "expansion_port_version", "steps_hash"],
)
def test_pins_from_payload_raises_when_required_key_missing(missing_key: str) -> None:
    """Parametrized: each of the 4 required keys must surface
    RecipeExpansionRecordNotFoundError when absent."""
    full_payload: dict[str, object] = {
        "bindings": {"a": 1.0},
        "bindings_hash": "abc",
        "expansion_port_version": "v1",
        "steps_hash": "def",
        "recipe_version": "v1",
    }
    payload = {k: v for k, v in full_payload.items() if k != missing_key}
    with pytest.raises(RecipeExpansionRecordNotFoundError) as exc:
        pins_from_payload(_PROCEDURE_ID, payload)
    assert exc.value.procedure_id == _PROCEDURE_ID


@pytest.mark.unit
def test_verify_bindings_hash_with_matching_hash_returns_none() -> None:
    pins = _pins()
    assert verify_bindings_hash(_PROCEDURE_ID, pins) is None


@pytest.mark.unit
def test_verify_bindings_hash_with_mismatch_raises_with_bindings_discriminator() -> None:
    base = _pins()
    drifted = RecipeExpansionPins(
        recipe_version=base.recipe_version,
        bindings=base.bindings,
        bindings_hash="0" * 64,
        steps_hash=base.steps_hash,
        expansion_port_version=base.expansion_port_version,
    )
    with pytest.raises(RecipeExpansionReplayMismatchError) as exc:
        verify_bindings_hash(_PROCEDURE_ID, drifted)
    assert exc.value.procedure_id == _PROCEDURE_ID
    assert exc.value.mismatch_field == "bindings"


@pytest.mark.unit
def test_verify_steps_hash_with_matching_hash_returns_none() -> None:
    pins = _pins()
    steps = (SetpointStep(address="dev:x", value=1.0),)
    assert verify_steps_hash(_PROCEDURE_ID, steps, pins) is None


@pytest.mark.unit
def test_verify_steps_hash_with_mismatch_raises_with_steps_discriminator() -> None:
    pins = _pins()
    drifted_steps = (SetpointStep(address="dev:x", value=999.0),)
    with pytest.raises(RecipeExpansionReplayMismatchError) as exc:
        verify_steps_hash(_PROCEDURE_ID, drifted_steps, pins)
    assert exc.value.procedure_id == _PROCEDURE_ID
    assert exc.value.mismatch_field == "steps"


@pytest.mark.unit
def test_verify_bindings_hash_uses_canonical_json_bytes_byte_equal_to_at_write() -> None:
    """Bindings hash reproduces against the EXACT same canonical-JSON
    bytes the  at-write decider used (single-source via
    cora.shared.canonical_json). A divergence would silently
    break replay verification for in-flight Procedures."""
    bindings = {"beta": 2.0, "alpha": 1.0}
    direct = hashlib.sha256(
        json.dumps(bindings, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    via_helper = hashlib.sha256(canonical_json_bytes(dict(bindings))).hexdigest()
    assert direct == via_helper
