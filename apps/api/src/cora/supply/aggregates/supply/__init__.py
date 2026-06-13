"""Supply aggregate: state, enums (status / trigger), errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.supply.features.<verb>_supply/` and import from here for state
and event types.

Public surface: enums + VOs + errors + events + evolver +
load_supply. 10a-a shipped genesis + first transition;
10a-b closed the FSM with 4 more transition events + 4 more errors
covering the degradation/recovery cycle.
"""

from cora.supply.aggregates.supply.events import (
    SupplyDegraded,
    SupplyDeregistered,
    SupplyEvent,
    SupplyMarkedAvailable,
    SupplyMarkedRecovering,
    SupplyMarkedUnavailable,
    SupplyRegistered,
    SupplyRestored,
    TriggeredBy,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.supply.aggregates.supply.evolver import evolve, fold
from cora.supply.aggregates.supply.read import load_supply
from cora.supply.aggregates.supply.state import (
    SUPPLY_KIND_MAX_LENGTH,
    SUPPLY_NAME_MAX_LENGTH,
    InvalidMonitorRefError,
    InvalidSupplyKindError,
    InvalidSupplyNameError,
    InvalidSupplyReasonError,
    MonitorRef,
    MonitorTriggerNotPermittedError,
    Supply,
    SupplyAlreadyExistsError,
    SupplyCannotDegradeError,
    SupplyCannotDeregisterError,
    SupplyCannotMarkAvailableError,
    SupplyCannotMarkRecoveringError,
    SupplyCannotMarkUnavailableError,
    SupplyCannotRestoreError,
    SupplyContainingAssetNotFoundError,
    SupplyFacilityNotFoundError,
    SupplyName,
    SupplyNotFoundError,
    SupplyReason,
    SupplyStatus,
    TriggerSource,
)

__all__ = [
    "SUPPLY_KIND_MAX_LENGTH",
    "SUPPLY_NAME_MAX_LENGTH",
    "InvalidMonitorRefError",
    "InvalidSupplyKindError",
    "InvalidSupplyNameError",
    "InvalidSupplyReasonError",
    "MonitorRef",
    "MonitorTriggerNotPermittedError",
    "Supply",
    "SupplyAlreadyExistsError",
    "SupplyCannotDegradeError",
    "SupplyCannotDeregisterError",
    "SupplyCannotMarkAvailableError",
    "SupplyCannotMarkRecoveringError",
    "SupplyCannotMarkUnavailableError",
    "SupplyCannotRestoreError",
    "SupplyContainingAssetNotFoundError",
    "SupplyDegraded",
    "SupplyDeregistered",
    "SupplyEvent",
    "SupplyFacilityNotFoundError",
    "SupplyMarkedAvailable",
    "SupplyMarkedRecovering",
    "SupplyMarkedUnavailable",
    "SupplyName",
    "SupplyNotFoundError",
    "SupplyReason",
    "SupplyRegistered",
    "SupplyRestored",
    "SupplyStatus",
    "TriggerSource",
    "TriggeredBy",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_supply",
    "to_payload",
]
