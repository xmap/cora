"""Evolver: replay events to reconstruct Dataset state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `DatasetEvent` without a matching match arm here.

Status mapping per event type:
  - `DatasetRegistered` -> REGISTERED  (genesis); intent defaults to TRIAL
  - `DatasetDiscarded`  -> DISCARDED   (terminal)
  - `DatasetPromoted`   -> status preserved (orthogonal to lifecycle;
                                              flips intent to PRODUCTION; 7e)

The mapping is hardcoded per match arm; the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as the rest of the codebase.

**Critical invariant**: every transition arm MUST carry every
Dataset field through from prior state. Constructing
`Dataset(id=..., name=..., uri=..., checksum=..., byte_size=...,
encoding=..., status=...)` without explicitly passing the optional
cross-aggregate refs (`producing_run_id`, `producing_procedure_id`,
`subject_id`, `derived_from`) AND the additive fields
(`producing_run_end_state`, `producing_actuation_kind`, `intent`,
`used_calibration_ids`) would silently WIPE them to defaults.
Aligned to explicit construction post-domain-audit to match the
documented pattern in Asset/Plan/Method/Practice/Family/Subject/Run
evolvers. The `used_calibration_ids` AsShot citation set is IMMUTABLE
after register — every transition arm preserves
`prior.used_calibration_ids` verbatim (mirrors Run.pinned_calibration_ids
AsShot immutability).

Defensive guard: `DatasetDiscarded` and `DatasetPromoted` arms raise
on `state is None` (the parent Dataset must exist before any
transition event). If a stream contains a transition without a prior
DatasetRegistered, the stream is corrupted and the evolver fails
loud. The `require_state` helper keeps per-arm bodies short.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.data.aggregates.dataset.events import (
    DatasetDemoted,
    DatasetDiscarded,
    DatasetEvent,
    DatasetPromoted,
    DatasetRegistered,
)
from cora.data.aggregates.dataset.state import (
    Dataset,
    DatasetChecksum,
    DatasetEncoding,
    DatasetName,
    DatasetStatus,
    DatasetUri,
    Intent,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Dataset | None, event: DatasetEvent) -> Dataset:
    """Apply one event to the current state."""
    match event:
        case DatasetRegistered(
            dataset_id=dataset_id,
            name=name,
            uri=uri,
            checksum_algorithm=checksum_algorithm,
            checksum_value=checksum_value,
            byte_size=byte_size,
            media_type=media_type,
            conforms_to=conforms_to,
            producing_run_id=producing_run_id,
            producing_procedure_id=producing_procedure_id,
            subject_id=subject_id,
            derived_from=derived_from,
            producing_run_end_state=producing_run_end_state,
            producing_actuation_kind=producing_actuation_kind,
            intent=intent,
            used_calibration_ids=used_calibration_ids,
        ):
            _ = state  # DatasetRegistered is the genesis event; prior state ignored.
            return Dataset(
                id=dataset_id,
                name=DatasetName(name),
                uri=DatasetUri(uri),
                checksum=DatasetChecksum(
                    algorithm=checksum_algorithm,
                    value=checksum_value,
                ),
                byte_size=byte_size,
                encoding=DatasetEncoding(
                    media_type=media_type,
                    conforms_to=conforms_to,
                ),
                producing_run_id=producing_run_id,
                producing_procedure_id=producing_procedure_id,
                subject_id=subject_id,
                derived_from=derived_from,
                status=DatasetStatus.REGISTERED,
                # carry from event payload (default-handled
                # via payload.get for legacy events in from_stored).
                producing_run_end_state=producing_run_end_state,
                producing_actuation_kind=producing_actuation_kind,
                intent=Intent(intent),
                # AsShot citation set at genesis (frozenset for
                # in-memory equality semantics; the event carries a tuple
                # for deterministic wire byte ordering).
                used_calibration_ids=frozenset(used_calibration_ids),
            )
        case DatasetDiscarded():
            prior = require_state(state, "DatasetDiscarded")
            return Dataset(
                id=prior.id,
                name=prior.name,
                uri=prior.uri,
                checksum=prior.checksum,
                byte_size=prior.byte_size,
                encoding=prior.encoding,
                producing_run_id=prior.producing_run_id,
                producing_procedure_id=prior.producing_procedure_id,
                subject_id=prior.subject_id,
                derived_from=prior.derived_from,
                status=DatasetStatus.DISCARDED,
                # carry-through: discard preserves intent +
                # producing_run_end_state (audit-relevant historical artifacts).
                producing_run_end_state=prior.producing_run_end_state,
                producing_actuation_kind=prior.producing_actuation_kind,
                intent=prior.intent,
                # AsShot invariant: never change after register.
                used_calibration_ids=prior.used_calibration_ids,
            )
        case DatasetPromoted():
            prior = require_state(state, "DatasetPromoted")
            return Dataset(
                id=prior.id,
                name=prior.name,
                uri=prior.uri,
                checksum=prior.checksum,
                byte_size=prior.byte_size,
                encoding=prior.encoding,
                producing_run_id=prior.producing_run_id,
                producing_procedure_id=prior.producing_procedure_id,
                subject_id=prior.subject_id,
                derived_from=prior.derived_from,
                # Status preserved (intent is orthogonal to lifecycle).
                status=prior.status,
                producing_run_end_state=prior.producing_run_end_state,
                producing_actuation_kind=prior.producing_actuation_kind,
                # The state change: intent flips Trial -> Production.
                intent=Intent.PRODUCTION,
                # AsShot invariant: never change after register.
                used_calibration_ids=prior.used_calibration_ids,
            )
        case DatasetDemoted():
            prior = require_state(state, "DatasetDemoted")
            return Dataset(
                id=prior.id,
                name=prior.name,
                uri=prior.uri,
                checksum=prior.checksum,
                byte_size=prior.byte_size,
                encoding=prior.encoding,
                producing_run_id=prior.producing_run_id,
                producing_procedure_id=prior.producing_procedure_id,
                subject_id=prior.subject_id,
                derived_from=prior.derived_from,
                # Status preserved (intent is orthogonal to lifecycle).
                status=prior.status,
                producing_run_end_state=prior.producing_run_end_state,
                producing_actuation_kind=prior.producing_actuation_kind,
                # The state change: intent flips Production -> Retracted
                # (terminal Intent value; no re-promote from Retracted per
                # [[project-dataset-demote-design]] lock).
                intent=Intent.RETRACTED,
                # AsShot invariant: never change after register.
                used_calibration_ids=prior.used_calibration_ids,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[DatasetEvent]) -> Dataset | None:
    """Replay a stream of events from the empty initial state."""
    state: Dataset | None = None
    for event in events:
        state = evolve(state, event)
    return state
