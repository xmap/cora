"""LanguageModel aggregate: status FSM, serving route, cost-basis union,
tier axes, bounded-text VOs, errors, events, evolver, read repo.

The facility's catalog entry for one approved LLM, homed in the agent
BC beside the fleet whose `Agent.model_ref` it governs. Design lock:
[[project_model_catalog_design]].

Vertical slices that operate on this aggregate live under
`cora.agent.features.<verb>_language_model/` and import from here for
state and event types.

Public surface: enums + VOs + cost-basis union + errors + events +
evolver + load_language_model. `ModelRef` is deliberately NOT
re-exported here; its home stays the Agent aggregate (this entry
reuses the same VO so an agent's declared model and a catalog entry
compare field-for-field).
"""

from cora.agent.aggregates.language_model.events import (
    LanguageModelApproved,
    LanguageModelDefined,
    LanguageModelDeprecated,
    LanguageModelEvent,
    LanguageModelRetired,
    LanguageModelRetirementAnnounced,
    cost_basis_from_payload,
    cost_basis_to_payload,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.agent.aggregates.language_model.evolver import evolve, fold
from cora.agent.aggregates.language_model.read import load_language_model
from cora.agent.aggregates.language_model.state import (
    ENDPOINT_NOTE_MAX_LENGTH,
    LANGUAGE_MODEL_NAME_MAX_LENGTH,
    ArchivabilityTier,
    CostBasis,
    DataSensitivityTier,
    EndpointNote,
    GpuHourPricing,
    InvalidCostBasisError,
    InvalidEndpointNoteError,
    InvalidLanguageModelNameError,
    InvalidLanguageModelReasonError,
    LanguageModel,
    LanguageModelAlreadyExistsError,
    LanguageModelCannotAnnounceRetirementError,
    LanguageModelCannotApproveError,
    LanguageModelCannotDeprecateError,
    LanguageModelCannotRetireError,
    LanguageModelName,
    LanguageModelNotApprovedError,
    LanguageModelNotFoundError,
    LanguageModelReason,
    LanguageModelStatus,
    ServingRoute,
    TokenPricing,
)

__all__ = [
    "ENDPOINT_NOTE_MAX_LENGTH",
    "LANGUAGE_MODEL_NAME_MAX_LENGTH",
    "ArchivabilityTier",
    "CostBasis",
    "DataSensitivityTier",
    "EndpointNote",
    "GpuHourPricing",
    "InvalidCostBasisError",
    "InvalidEndpointNoteError",
    "InvalidLanguageModelNameError",
    "InvalidLanguageModelReasonError",
    "LanguageModel",
    "LanguageModelAlreadyExistsError",
    "LanguageModelApproved",
    "LanguageModelCannotAnnounceRetirementError",
    "LanguageModelCannotApproveError",
    "LanguageModelCannotDeprecateError",
    "LanguageModelCannotRetireError",
    "LanguageModelDefined",
    "LanguageModelDeprecated",
    "LanguageModelEvent",
    "LanguageModelName",
    "LanguageModelNotApprovedError",
    "LanguageModelNotFoundError",
    "LanguageModelReason",
    "LanguageModelRetired",
    "LanguageModelRetirementAnnounced",
    "LanguageModelStatus",
    "ServingRoute",
    "TokenPricing",
    "cost_basis_from_payload",
    "cost_basis_to_payload",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_language_model",
    "to_payload",
]
