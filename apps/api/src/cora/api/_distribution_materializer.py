"""DistributionMaterializer: leg B of stage-then-reconstruct.

Sequences the three acts that turn "bytes copied to another tier" into a fact
CORA trusts: (1) move the bytes over a `TransferPort`, (2) on success record a
new `Distribution` of the SAME raw Dataset at the analysis-tier Storage Supply
(`register_distribution`), (3) record a checksum `Attestation` over the landed
bytes (`record_attestation`), whose Match flips the Distribution to Verified in
the Data BC projection. That Verified-at-tier fact is exactly what leg C's
start_run gate reads ([[project_run_input_dependency_design]]).

This is an orchestration concern, so it lives in `cora.api` (the only module
that may reach both `cora.operation.ports` and the Data BC handlers). It is the
materialize edge job the EdgeConductor will drive; here it is a self-contained
unit with injected collaborators, exercised against fakes.

## What it owns vs trusts

It OWNS the sequence and the transfer gate: it begins the transfer, polls
`observe` to a terminal (a non-terminal `Suspended` just keeps polling; there is
no special Suspended path yet), and registers ONLY if the transfer Succeeded. It
TRUSTS the caller's `RegisterDistribution`: the
caller (which holds the parent Dataset) builds it with the byte-identical-copy
fields (checksum / byte_size / media_type equal to the parent Dataset); the
Data BC decider enforces that equality. The `RecordAttestation` is built here
from the registration's `dataset_id` plus the new Distribution id.

## Eventual-consistency note

`record_attestation` returns an attestation id for Match, Mismatch, AND
Unreachable; the Distribution's flip to Verified (Match) or Stale (Mismatch) is
a projection-only update the Data BC applies from `AttestationRecorded`. So a
successful `materialize` means "moved + registered + attested", not "Verified";
the Verified status is the projection's eventual flip, which leg C's gate reads
later. This mirrors the safety-envelope eventual-consistency window.

## Deferred

A long-running continuous sync would complete via a later signal rather than a
synchronous observe-loop; this unit polls to a terminal with a runaway bound and
NO inter-poll backoff (a busy-spin that is fakes-only safe, see
`_observe_to_terminal`). Real-adapter poll backoff, a real `Suspended`
intervention path, and the signal-driven variant are deferred to the
first-real-adapter trigger; none may be skipped when this is wired to a live
substrate (Globus first).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cora.data.features.record_attestation.command import RecordAttestation
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.ports.transfer_port import TransferState

if TYPE_CHECKING:
    from uuid import UUID

    from cora.data.features.record_attestation.handler import Handler as RecordAttestationHandler
    from cora.data.features.register_distribution.command import RegisterDistribution
    from cora.data.features.register_distribution.handler import (
        Handler as RegisterDistributionHandler,
    )
    from cora.operation.ports.transfer_port import (
        TransferHandle,
        TransferPort,
        TransferProgress,
        TransferRequest,
    )

_MAX_OBSERVATIONS = 10_000
"""Runaway bound on the observe-loop. A real transfer reaches a terminal in far
fewer polls; this is a backstop against a substrate that never terminates, not a
tuning knob. Exceeding it raises rather than spinning forever."""

_CHECKSUM_VERIFIED_KIND = "ChecksumVerified"
"""The AttestationKind wire value the materialize edge job requests. Mirrored as
a literal because `cora.api` may not import `cora.data.aggregates` (tach); the
record_attestation handler re-validates it against the closed AttestationKind."""


@dataclass(frozen=True)
class MaterializationOutcome:
    """The result of one materialize: the transfer terminal plus what it recorded.

    `distribution_id` and `attestation_id` are None when the transfer did not
    Succeed (nothing is registered off an incomplete move). `materialized` is the
    one-call success predicate. `transfer_state` and `transfer_detail` carry the
    terminal observation so a caller can record why a non-success move stopped.
    """

    transfer_state: TransferState
    distribution_id: UUID | None = None
    attestation_id: UUID | None = None
    transfer_detail: str | None = None

    @property
    def materialized(self) -> bool:
        """True iff the move Succeeded and a Distribution was registered."""
        return self.distribution_id is not None


@dataclass
class DistributionMaterializer:
    """Drives transfer -> register_distribution -> record_attestation.

    Construct with a `TransferPort` and the two Data BC handlers (the bare
    `Handler` protocols `register_distribution.bind` / `record_attestation.bind`
    return); call `materialize` per move. See the module docstring for what it
    owns vs trusts.
    """

    transfer_port: TransferPort
    register_distribution: RegisterDistributionHandler
    record_attestation: RecordAttestationHandler

    async def materialize(
        self,
        transfer: TransferRequest,
        registration: RegisterDistribution,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> MaterializationOutcome:
        """Move the bytes, then (only on success) register + attest the copy.

        Returns a `MaterializationOutcome`. A non-Succeeded transfer terminal
        short-circuits with no Distribution registered. Transfer-port errors and
        Data BC domain errors propagate to the caller unchanged.
        """
        handle = await self.transfer_port.begin(transfer)
        progress = await self._observe_to_terminal(handle)
        if progress.state is not TransferState.SUCCEEDED:
            return MaterializationOutcome(
                transfer_state=progress.state, transfer_detail=progress.detail
            )

        distribution_id = await self.register_distribution(
            registration,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
        )
        attestation_id = await self.record_attestation(
            RecordAttestation(
                dataset_id=registration.dataset_id,
                distribution_id=distribution_id,
                kind=_CHECKSUM_VERIFIED_KIND,
            ),
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
        )
        return MaterializationOutcome(
            transfer_state=TransferState.SUCCEEDED,
            distribution_id=distribution_id,
            attestation_id=attestation_id,
            transfer_detail=progress.detail,
        )

    async def _observe_to_terminal(self, handle: TransferHandle) -> TransferProgress:
        """Poll `observe` until a terminal; every non-terminal state just re-polls.

        A non-terminal observation (`Pending` / `Active` / `Suspended`) falls
        through to the next poll: the loop does NOT fold on `Suspended`, but it
        also does NOT special-case it (no longer wait, no credential-renewal
        backoff). "Waiting through Suspended" here means "keeps polling," not
        "waits patiently"; a real Suspended handling path is deferred.

        BUSY-SPIN, FAKES-ONLY: there is NO delay between polls. A test double
        returns a terminal on the first poll or two, so the spin never bites
        here. Against a REAL adapter this hammers `observe()` up to
        `_MAX_OBSERVATIONS` times with zero backoff, which either trips the
        substrate's rate limit or burns the whole budget in seconds and raises
        long before an hours-long transfer finishes. A real adapter MUST gain
        poll backoff (or the deferred signal-driven terminalization) BEFORE this
        is wired to one; see the module docstring "Deferred". `_MAX_OBSERVATIONS`
        is a runaway backstop only, not a substitute for backoff.
        """
        for _ in range(_MAX_OBSERVATIONS):
            progress = await self.transfer_port.observe(handle)
            if progress.state.is_terminal:
                return progress
        msg = (
            f"transfer {handle!r} did not reach a terminal within {_MAX_OBSERVATIONS} observations"
        )
        raise RuntimeError(msg)


__all__ = ["DistributionMaterializer", "MaterializationOutcome"]
