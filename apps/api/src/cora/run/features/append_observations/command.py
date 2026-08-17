"""The `AppendObservations` command, intent dataclass for this slice.

Batch shape from day one (matches `append_inferences`
precedent from Decision BC). Length-1 batches are the degenerate
case; same code path either way. Anticipates DAQ-adapter
integration which will batch naturally.

Producer-supplied `event_id` (UUIDv7) per entry; store dedups via
Postgres PK (`ON CONFLICT (event_id) DO NOTHING`). At-least-once
semantics for free.

## Lazy open-on-first-write

The handler loads the parent Run, checks whether
`run.observation_logbook_id` is set, and emits a
`RunObservationLogbookOpened` event lazily on first write. `start_run`
stays unchanged; the logbook attaches when the first
observation arrives. Per [[project_run_reading_design]] §Decision and
[[project_logbook_entry_storage]].

## Polymorphic by sampling_procedure

All entries share the same row shape `(channel_name, value?,
categorical_value?, units?, sampled_at, sampling_procedure)`. The
`sampling_procedure` field discriminates baseline vs monitor vs
future-additive kinds. SOSA-aligned (W3C SOSA 2023
`sosa:samplingProcedure`).

## value vs categorical_value

Exactly one is set per entry: `value` for a numeric reading,
`categorical_value` for an enum-label reading (`ControlPort`'s
`Measurement(kind="Categorical")`, carried as the facility's own
substrate label). The handler raises `InvalidObservationShapeError`
when neither or both are set; the DB enforces the same invariant via
an exclusive-arc CHECK constraint.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ObservationInput:
    """One observation entry's input payload from the producer.

    Mirrors `Observation` but omits the CORA-infra fields (run_id /
    logbook_id / actor_id / command_name / correlation_id /
    causation_id) which are populated by the handler from the URL
    path + envelope.
    """

    event_id: UUID
    channel_name: str
    value: float | None
    sampled_at: datetime
    sampling_procedure: str
    units: str | None = None
    occurred_at: datetime | None = None
    """When the handler appended the entry. Optional from the producer
    — when omitted, the handler defaults to `clock.now()`. Producers
    that have a separate ingest-time clock (DAQ adapters with their
    own buffering) can populate this explicitly."""
    is_simulated: bool = False
    """Provenance: True only when a sim / replay feeder produced this
    value. Defaults to False (real), the safe direction for the
    closed-loop gate: a real adapter that omits the flag is treated as
    real. Only the sim feeder sets it True."""
    categorical_value: str | None = None
    """Set instead of `value` for an enum-label reading. Exactly one of
    the two must be set; numeric producers omit this field entirely and
    rely on the default."""


@dataclass(frozen=True)
class AppendObservations:
    """Append a batch of observations to a Run's observation logbook."""

    run_id: UUID
    entries: tuple[ObservationInput, ...]
