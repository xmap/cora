"""Operation BC ports (BC-tier Protocols owned by Operation).

`ControlPort` ships here per
[[project_control_port_generalization_research]] (supersedes the
earlier `PvDriver` lock from [[project_control_port_design]]).
Domain-shaped value-IO; substrate adapters serve as ACLs translating
EPICS / Tango / OPC UA wire vocabularies into the CORA-owned
`Measurement` + `MeasurementKind` + `Quality` value types.

BC-tier port location per [[project_adapter_naming_design]]: stays
here until rule-of-three promotes to `cora.infrastructure.ports`.
Sibling ports `CommandPort` (RPC) and `EventPort` (typed events) are
deferred to first concrete consumer per adapter-first discipline.

`ComputePort` is the CONDUCT sibling: domain-shaped compute-job
submission (submit / await / fetch artifact), distilled from a single
local-process adapter. A routing registry is deferred to the second
real substrate, exactly as ControlPort earned its registry.

`TransferPort` is the data-movement sibling: domain-shaped byte movement
(begin / observe / cancel), non-blocking because a transfer can be long
running, can suspend mid-flight, and can finish partially. It ships with
a test double only, pending the build trigger; see its module docstring.
"""

from cora.operation.ports.compute_port import (
    ArtifactNotFoundError,
    ArtifactRef,
    ComputeJobFailedError,
    ComputeNotAvailableError,
    ComputePort,
    ComputeResources,
    ComputeResult,
    ComputeStatus,
    ComputeSubmitRejectedError,
    ComputeTimeoutError,
    JobId,
    JobSpec,
    MeasurementNotFoundError,
)
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlPort,
    ControlTimeoutError,
    ControlValueCoercionError,
    ControlWriteRejectedError,
    ControlWritesDisabledError,
    NoAdapterForAddressError,
)
from cora.operation.ports.measurement import (
    Measurement,
    MeasurementKind,
    Quality,
)
from cora.operation.ports.procedure_activity_lookup import (
    InMemoryProcedureActivityLookup,
    ProcedureActivityLookup,
    ProcedureActivityRecency,
)
from cora.operation.ports.procedure_outcome_lookup import (
    ProcedureOutcomeLookup,
    RecordedOutcome,
)
from cora.operation.ports.transfer_port import (
    NoRouteForLocationError,
    TransferAccessDeniedError,
    TransferEndpointUnreachableError,
    TransferHandle,
    TransferIntegrityError,
    TransferPort,
    TransferProgress,
    TransferRejectedError,
    TransferRequest,
    TransferState,
    TransferTimeoutError,
)

__all__ = [
    "ArtifactNotFoundError",
    "ArtifactRef",
    "ComputeJobFailedError",
    "ComputeNotAvailableError",
    "ComputePort",
    "ComputeResources",
    "ComputeResult",
    "ComputeStatus",
    "ComputeSubmitRejectedError",
    "ComputeTimeoutError",
    "ControlAccessDeniedError",
    "ControlNotConnectedError",
    "ControlPort",
    "ControlTimeoutError",
    "ControlValueCoercionError",
    "ControlWriteRejectedError",
    "ControlWritesDisabledError",
    "InMemoryProcedureActivityLookup",
    "JobId",
    "JobSpec",
    "Measurement",
    "MeasurementKind",
    "MeasurementNotFoundError",
    "NoAdapterForAddressError",
    "NoRouteForLocationError",
    "ProcedureActivityLookup",
    "ProcedureActivityRecency",
    "ProcedureOutcomeLookup",
    "Quality",
    "RecordedOutcome",
    "TransferAccessDeniedError",
    "TransferEndpointUnreachableError",
    "TransferHandle",
    "TransferIntegrityError",
    "TransferPort",
    "TransferProgress",
    "TransferRejectedError",
    "TransferRequest",
    "TransferState",
    "TransferTimeoutError",
]
