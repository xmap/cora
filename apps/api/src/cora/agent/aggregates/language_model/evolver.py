"""Evolver: replay events to reconstruct LanguageModel state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `LanguageModelEvent` without a matching match arm here.

Status mapping per event type:

  - `LanguageModelDefined`             -> DEFINED (genesis)
  - `LanguageModelApproved`            -> APPROVED (single-source:
                                          Defined only)
  - `LanguageModelRetirementAnnounced` -> RETIREMENT_ANNOUNCED
                                          (single-source: Approved;
                                          sets `retirement_effective_at`
                                          + `end_reason`)
  - `LanguageModelRetired`             -> RETIRED (source: Approved |
                                          RetirementAnnounced; overwrites
                                          `end_reason` only when the event
                                          carries a reason, so a reasonless
                                          removal keeps the announcement's)
  - `LanguageModelDeprecated`          -> DEPRECATED (source: Defined |
                                          Approved | RetirementAnnounced;
                                          sets `end_reason`)

Source-state guards live at the decider, NOT here; the evolver trusts
the event log (folded events have already passed their decider).

Transition arms use `dataclasses.replace`, which carries every
untouched field forward by construction, so the silent-wipe bug class
the Agent evolver guards against field-by-field cannot occur here.

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver`.
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import assert_never

from cora.agent.aggregates.agent import ModelRef
from cora.agent.aggregates.language_model.events import (
    LanguageModelApproved,
    LanguageModelDefined,
    LanguageModelDeprecated,
    LanguageModelEvent,
    LanguageModelRetired,
    LanguageModelRetirementAnnounced,
    cost_basis_from_payload,
)
from cora.agent.aggregates.language_model.state import (
    ArchivabilityTier,
    DataSensitivityTier,
    EndpointNote,
    LanguageModel,
    LanguageModelName,
    LanguageModelReason,
    LanguageModelStatus,
    ServingRoute,
)
from cora.infrastructure.evolver import require_state


def evolve(state: LanguageModel | None, event: LanguageModelEvent) -> LanguageModel:
    """Apply one event to the current state."""
    match event:
        case LanguageModelDefined(
            language_model_id=language_model_id,
            name=name,
            provider=provider,
            model=model,
            snapshot_pin=snapshot_pin,
            served_via=served_via,
            endpoint_note=endpoint_note,
            cost_basis=cost_basis,
            data_tier=data_tier,
            archivability=archivability,
        ):
            _ = state  # LanguageModelDefined is the genesis event; prior state ignored
            return LanguageModel(
                id=language_model_id,
                name=LanguageModelName(name),
                model_ref=ModelRef(provider=provider, model=model, snapshot_pin=snapshot_pin),
                served_via=ServingRoute(served_via),
                cost_basis=cost_basis_from_payload(cost_basis),
                data_tier=DataSensitivityTier(data_tier),
                archivability=ArchivabilityTier(archivability),
                endpoint_note=(EndpointNote(endpoint_note) if endpoint_note is not None else None),
                status=LanguageModelStatus.DEFINED,
            )
        case LanguageModelApproved():
            prior = require_state(state, "LanguageModelApproved")
            return replace(prior, status=LanguageModelStatus.APPROVED)
        case LanguageModelRetirementAnnounced(reason=reason, effective_at=effective_at):
            prior = require_state(state, "LanguageModelRetirementAnnounced")
            return replace(
                prior,
                status=LanguageModelStatus.RETIREMENT_ANNOUNCED,
                retirement_effective_at=effective_at,
                end_reason=LanguageModelReason(reason),
            )
        case LanguageModelRetired(reason=reason):
            prior = require_state(state, "LanguageModelRetired")
            # A reasonless (unannounced) removal keeps the announcement's
            # reason: the folded state should never LOSE end-of-life
            # context on the way to terminal.
            return replace(
                prior,
                status=LanguageModelStatus.RETIRED,
                end_reason=(
                    LanguageModelReason(reason) if reason is not None else prior.end_reason
                ),
            )
        case LanguageModelDeprecated(reason=reason):
            prior = require_state(state, "LanguageModelDeprecated")
            return replace(
                prior,
                status=LanguageModelStatus.DEPRECATED,
                end_reason=LanguageModelReason(reason),
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[LanguageModelEvent]) -> LanguageModel | None:
    """Replay a stream of events from the empty initial state."""
    state: LanguageModel | None = None
    for event in events:
        state = evolve(state, event)
    return state
