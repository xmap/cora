"""Pure decider for the `DefineLanguageModel` command.

Pure function: given the current LanguageModel state (None for a
fresh stream) and a `DefineLanguageModel` command, returns the
events to append on the LanguageModel stream. No I/O, no awaits, no
side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports (the non-determinism principle: capture,
don't recompute).

## Validation

  - State must be None (genesis-only) ->
    `LanguageModelAlreadyExistsError`
  - `name` wrapped via `LanguageModelName(...)`; 1-120 chars after
    trim -> `InvalidLanguageModelNameError`
  - `provider` / `model` / `snapshot_pin` wrapped via `ModelRef(...)`
    (the Agent aggregate's VO, reused so a catalog entry and an
    agent's declared model compare field-for-field) ->
    `InvalidModelRefError`
  - `served_via` / `data_tier` / `archivability` wrapped via their
    StrEnums; an unknown value raises the enum's own `ValueError`.
    The HTTP / MCP boundary types these as the StrEnums (422 on
    unknowns), so the bare ValueError only ever fires for
    programmatic callers.
  - `endpoint_note` wrapped via `EndpointNote(...)` when not None;
    1-500 chars after trim -> `InvalidEndpointNoteError`. None is
    allowed (means no note).
  - `cost_basis` decoded via `cost_basis_from_payload(...)`; a
    missing or unknown `kind` and a negative or non-finite rate both
    surface from the helper as ValueError and are re-raised here as
    `InvalidCostBasisError`, so the route's 400 mapping catches ONE
    class for every malformed cost basis.

The event carries the RE-ENCODED cost basis
(`cost_basis_to_payload(decoded)`), not the caller's dict: decoding
then re-encoding guarantees the stored payload carries exactly the
canonical key set per kind (deterministic payload bytes for
idempotency replay) and drops any extraneous keys a caller smuggled
in.

Initial status is implicit `Defined` (event type IS the state-change
indicator; the genesis evolver hardcodes the mapping).
"""

from datetime import datetime
from uuid import UUID

from cora.agent.aggregates.agent import ModelRef
from cora.agent.aggregates.language_model import (
    ArchivabilityTier,
    DataSensitivityTier,
    EndpointNote,
    InvalidCostBasisError,
    LanguageModel,
    LanguageModelAlreadyExistsError,
    LanguageModelDefined,
    LanguageModelName,
    ServingRoute,
    cost_basis_from_payload,
    cost_basis_to_payload,
)
from cora.agent.features.define_language_model.command import DefineLanguageModel


def decide(
    state: LanguageModel | None,
    command: DefineLanguageModel,
    *,
    now: datetime,
    new_id: UUID,
) -> list[LanguageModelDefined]:
    """Decide the events produced by defining a new LanguageModel entry.

    Invariants:
      - State must be None (genesis-only)
        -> LanguageModelAlreadyExistsError
      - Name must be valid -> InvalidLanguageModelNameError
        (via LanguageModelName VO)
      - provider / model / snapshot_pin must form a valid ModelRef
        -> InvalidModelRefError (via ModelRef VO)
      - served_via / data_tier / archivability must be known enum
        values -> ValueError (via StrEnum construction)
      - Endpoint note (when set) must be valid
        -> InvalidEndpointNoteError (via EndpointNote VO)
      - Cost basis must decode to a known kind with finite
        non-negative rates -> InvalidCostBasisError
    """
    if state is not None:
        raise LanguageModelAlreadyExistsError(state.id)

    # Validate + trim via VOs / enums (each raises its own error on bad input).
    name = LanguageModelName(command.name)
    model_ref = ModelRef(
        provider=command.provider,
        model=command.model,
        snapshot_pin=command.snapshot_pin,
    )
    served_via = ServingRoute(command.served_via)
    data_tier = DataSensitivityTier(command.data_tier)
    archivability = ArchivabilityTier(command.archivability)

    endpoint_note: EndpointNote | None = None
    if command.endpoint_note is not None:
        endpoint_note = EndpointNote(command.endpoint_note)

    try:
        cost_basis = cost_basis_from_payload(command.cost_basis)
    except InvalidCostBasisError:
        raise
    except ValueError as exc:
        raise InvalidCostBasisError(str(exc)) from exc

    return [
        LanguageModelDefined(
            language_model_id=new_id,
            name=name.value,
            provider=model_ref.provider,
            model=model_ref.model,
            snapshot_pin=model_ref.snapshot_pin,
            served_via=served_via.value,
            endpoint_note=endpoint_note.value if endpoint_note is not None else None,
            cost_basis=cost_basis_to_payload(cost_basis),
            data_tier=data_tier.value,
            archivability=archivability.value,
            occurred_at=now,
        )
    ]
