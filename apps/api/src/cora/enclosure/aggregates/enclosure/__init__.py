"""Re-exports for the Enclosure aggregate.

Pattern matches `cora.federation.aggregates.facility.__init__`: events,
state (including the colocated `EnclosureName` VO + `InvalidEnclosureNameError`
+ `ENCLOSURE_NAME_MAX_LENGTH`), evolver, and BC-local id NewType
(`EnclosureId`) + payload-side VO (`EnclosureReason` + its error)
are all surfaced at the aggregate namespace so slices
import `from cora.enclosure.aggregates.enclosure import ...` without
reaching into individual modules.

This sub-slice scaffolds the aggregate shape only (state + enums +
events + evolver + VOs). Read helpers (`load_enclosure`) arrive in
subsequent sub-slices per [[project_enclosure_stage1_design]].
"""

from cora.enclosure.aggregates._value_types import (
    EnclosureId,
    EnclosureReason,
    InvalidEnclosureReasonError,
    InvalidMonitorRefError,
    MonitorRef,
)
from cora.enclosure.aggregates.enclosure.events import (
    EnclosureDecommissioned,
    EnclosureEvent,
    EnclosurePermitObserved,
    EnclosureRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.enclosure.aggregates.enclosure.evolver import evolve, fold
from cora.enclosure.aggregates.enclosure.state import (
    ENCLOSURE_NAME_MAX_LENGTH,
    Enclosure,
    EnclosureAlreadyExistsError,
    EnclosureCannotDecommissionError,
    EnclosureCannotObserveWhileDecommissionedError,
    EnclosureFacilityNotFoundError,
    EnclosureLifecycle,
    EnclosureName,
    EnclosureNotFoundError,
    EnclosurePermitStatus,
    InvalidEnclosureNameError,
    MonitorTriggerNotPermittedError,
)

__all__ = [
    "ENCLOSURE_NAME_MAX_LENGTH",
    "Enclosure",
    "EnclosureAlreadyExistsError",
    "EnclosureCannotDecommissionError",
    "EnclosureCannotObserveWhileDecommissionedError",
    "EnclosureDecommissioned",
    "EnclosureEvent",
    "EnclosureFacilityNotFoundError",
    "EnclosureId",
    "EnclosureLifecycle",
    "EnclosureName",
    "EnclosureNotFoundError",
    "EnclosurePermitObserved",
    "EnclosurePermitStatus",
    "EnclosureReason",
    "EnclosureRegistered",
    "InvalidEnclosureNameError",
    "InvalidEnclosureReasonError",
    "InvalidMonitorRefError",
    "MonitorRef",
    "MonitorTriggerNotPermittedError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "to_payload",
]
