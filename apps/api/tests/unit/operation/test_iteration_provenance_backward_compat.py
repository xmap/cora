"""Additive steering-provenance on ProcedureIterationEnded: round-trip + the
backward-compat guarantee that pre-existing payloads (missing the new keys)
deserialize to the absent defaults.

The provenance fields (advised_stop / reasoning / confidence /
confidence_source / alternatives / model_ref) are stream-only and additive:
`from_stored` reads them via `.get()`, so a Procedure stream written before
this slice rebuilds with None / () and never raises. The original required
keys (converged / reason) stay strict, so a payload missing them is still
Malformed.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.operation.aggregates.procedure import (
    ProcedureIterationEnded,
    from_stored,
    to_payload,
)
from cora.shared.decision_signals import DecisionConfidenceSource

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _stored(payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Procedure",
        stream_id=uuid4(),
        version=1,
        event_type="ProcedureIterationEnded",
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_iteration_ended_with_steering_provenance_round_trips() -> None:
    event = ProcedureIterationEnded(
        procedure_id=uuid4(),
        iteration_index=4,
        converged=None,
        reason=None,
        occurred_at=_NOW,
        advised_stop=False,
        reasoning="acquisition peak at 9.5 keV",
        confidence=0.82,
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        alternatives=("energy=9.0", "energy=10.0"),
        model_ref="grid_walk",
    )
    assert from_stored(_stored(to_payload(event))) == event


@pytest.mark.unit
def test_iteration_ended_stop_verdict_round_trips() -> None:
    event = ProcedureIterationEnded(
        procedure_id=uuid4(),
        iteration_index=7,
        converged=None,
        reason=None,
        occurred_at=_NOW,
        advised_stop=True,
        reasoning="grid exhausted",
        model_ref="grid_walk",
    )
    assert from_stored(_stored(to_payload(event))) == event


@pytest.mark.unit
def test_confidence_source_enum_is_type_faithful_round_trip() -> None:
    # The enum must survive to_payload (.value) -> from_stored (rebuild) as the
    # same enum member, not degrade to a plain str (the S4 writer feeds an enum).
    event = ProcedureIterationEnded(
        procedure_id=uuid4(),
        iteration_index=1,
        converged=None,
        reason=None,
        occurred_at=_NOW,
        advised_stop=False,
        confidence=0.5,
        confidence_source=DecisionConfidenceSource.LOGPROB,
    )
    rebuilt = from_stored(_stored(to_payload(event)))
    assert isinstance(rebuilt, ProcedureIterationEnded)
    assert rebuilt.confidence_source is DecisionConfidenceSource.LOGPROB
    assert rebuilt == event


@pytest.mark.unit
def test_pre_slice_payload_without_provenance_keys_deserializes_to_defaults() -> None:
    # A Procedure stream written before this slice: only the original keys.
    legacy_payload: dict[str, object] = {
        "procedure_id": str(uuid4()),
        "iteration_index": 2,
        "converged": True,
        "reason": "ok",
        "occurred_at": _NOW.isoformat(),
    }
    rebuilt = from_stored(_stored(legacy_payload))
    assert isinstance(rebuilt, ProcedureIterationEnded)
    assert rebuilt.converged is True
    assert rebuilt.advised_stop is None
    assert rebuilt.reasoning is None
    assert rebuilt.confidence is None
    assert rebuilt.confidence_source is None
    assert rebuilt.alternatives == ()
    assert rebuilt.model_ref is None


@pytest.mark.unit
def test_payload_missing_required_converged_key_still_raises_malformed() -> None:
    # The new provenance keys are optional (.get), but the original required
    # keys stay strict: a payload missing `converged` is Malformed even when
    # the provenance keys are present.
    payload: dict[str, object] = {
        "procedure_id": str(uuid4()),
        "iteration_index": 2,
        "reason": None,
        "occurred_at": _NOW.isoformat(),
        "advised_stop": True,
        "reasoning": "grid exhausted",
    }
    with pytest.raises(ValueError, match="Malformed ProcedureIterationEnded payload"):
        from_stored(_stored(payload))
