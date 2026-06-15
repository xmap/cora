"""The `AppendProcedureActivities` command, intent dataclass for this slice.

Batch shape from day one (matches `append_observations` and
`append_inferences` precedents). Length-1 batches are the
degenerate case; same code path either way. Anticipates EPICS
adapter integration which will batch step records naturally during
an alignment or characterization run.

Producer-supplied `event_id` (UUIDv7) per entry; store dedups via
Postgres PK (`ON CONFLICT (event_id) DO NOTHING`). At-least-once
semantics for free.

## Lazy open-on-first-write

The handler loads the parent Procedure, checks whether
`procedure.activity_logbook_id` is set, and emits a
`ProcedureActivitiesLogbookOpened` event lazily on first write.
`start_procedure` stays unchanged; the logbook
attaches when the first step arrives. Per [[project_operation_design]]
and [[project_logbook_entry_storage]].

## Polymorphic by step_kind + JSON payload

All entries share the same wrapper shape `(step_kind, payload,
sampled_at)`. The `step_kind` field discriminates setpoint / action /
check (CORA's rename of ISA-106's Command/Perform/Verify triplet);
`payload` carries the kind-specific body as a JSON-serializable dict.
Per-kind body shape is enforced at the API layer (per-kind Pydantic
models on the route); the handler defensively re-validates step_kind
against `STEP_KIND_VALUES` for direct in-process callers.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ActivityInput:
    """One step entry's input payload from the producer.

    Mirrors `Activity` but omits the CORA-infra fields
    (procedure_id / logbook_id / actor_id / command_name /
    correlation_id / causation_id) which are populated by the handler
    from the URL path + envelope.

    `payload` is a kind-specific JSON-serializable dict (per the
    polymorphic-with-discriminator + JSON pattern documented at
    [[project_operation_design]]). Per-kind body shape lives at the
    API layer via per-kind Pydantic models.
    """

    event_id: UUID
    step_kind: str
    payload: dict[str, Any]
    sampled_at: datetime
    occurred_at: datetime | None = None
    """When the handler appended the entry. Optional from the producer
    -- when omitted, the handler defaults to `clock.now()`. Producers
    that have a separate ingest-time clock (EPICS adapters with their
    own buffering) can populate this explicitly."""


@dataclass(frozen=True)
class AppendProcedureActivities:
    """Append a batch of steps to a Procedure's steps logbook."""

    procedure_id: UUID
    entries: tuple[ActivityInput, ...]
