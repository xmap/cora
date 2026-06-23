"""Vertical slice for the ``RecordAttestation`` command.

Module-as-namespace surface mirrors ``register_distribution``. The
operator command is slim: CORA verifies the Distribution's bytes itself
and derives the evidence.

    from cora.data.features import record_attestation

    cmd = record_attestation.RecordAttestation(
        dataset_id=dataset_id,
        distribution_id=distribution_id,
        kind="ChecksumVerified",
    )
    handler = record_attestation.bind(deps)
    attestation_id = await handler(cmd, principal_id=..., correlation_id=...)

The handler computes the outcome + evidence via the ChecksumVerifier port
and assembles an ``AttestationRecordingInput`` (the decider's input) before
calling ``decide``.
"""

from cora.data.features.record_attestation import tool
from cora.data.features.record_attestation.command import (
    AttestationRecordingInput,
    RecordAttestation,
)
from cora.data.features.record_attestation.context import (
    AttestationRecordingContext,
)
from cora.data.features.record_attestation.decider import decide
from cora.data.features.record_attestation.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.data.features.record_attestation.route import router

__all__ = [
    "AttestationRecordingContext",
    "AttestationRecordingInput",
    "Handler",
    "IdempotentHandler",
    "RecordAttestation",
    "bind",
    "decide",
    "router",
    "tool",
]
