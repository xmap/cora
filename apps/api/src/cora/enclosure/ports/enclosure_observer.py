"""EnclosureObserver port: substrate-driven permit-status observation stream.

`EnclosureObserver` is the BC-local async Protocol that the Enclosure
BC's Monitor-trigger runtime uses to drain permit-status observations
from the substrate (EPICS PV monitors, P4P PVA subscriptions, Tango
attribute callbacks, file-watch tails). Substrate details live behind
concrete adapters; the runtime never touches substrate-specific
symbols directly.

Per [[project_enclosure_stage1_design]] L-port-1 + L-CHARTER-4 this
port lives BC-local at `cora/enclosure/ports/` because:

  - The sole consumer is the Enclosure BC's own monitor-trigger
    runtime (the inbound adapter loop that calls
    `observe_enclosure_status`).
  - The seam is substrate-IO, not cross-BC contract.
  - There is zero cross-BC consumption: no other BC reads observations
    off this port.

Cross-BC lookup ports (consumed by Run / Operation / Asset start
handlers) land at `cora/infrastructure/ports/` per the conventional
two-home split; this port is the BC-local counterpart and is not
promoted to infrastructure.

## Domain vocabulary (substrate-neutral)

  - `EnclosureObservation`: one permit-status reading drained from the
    substrate, scoped by `enclosure_code` (the BC-local Enclosure
    identity surface adapters know). Carries the observed status as a
    string (parsed by the handler-side decider against
    `EnclosurePermitStatus`) plus the source attribution pair
    (`source_kind`, `source_id`) used to populate the event payload's
    `monitor_ref` wire string.
  - `EnclosureObserverScope`: the set of enclosure codes the substrate
    adapter should subscribe to. Empty scope is valid and yields no
    observations.

## Source attribution (separate fields, not colon-delimited)

`source_kind` and `source_id` ship as two independent strings on the
observation envelope. The two-field shape is preserved at the port
surface and joined into the colon-delimited `monitor_ref` payload
string by the handler / decider when the event is emitted.

The downstream `EnclosurePermitObserved` event keeps the
`monitor_ref: str | None` field with `"{source_kind}:{source_id}"`
encoding to match the Federation Slice 6E wire-omit-when-None
precedent. The split-vs-joined seam is the port-to-handler boundary.

## D6.L2 anti-lock posture

The only legitimate driver of `EnclosurePermitStatus.PERMITTED` is a
substrate observation drained through this port. There is no operator
gesture that asserts Permitted, no `force=True` override (D10-L1), no
Bypassed status (D10-L1). There is no `source_kind` discriminator
value that promotes an operator gesture into a Permitted observation;
every observation that crosses this seam represents a substrate
reading, and the inbound adapter is responsible for verifying that
constraint before invoking the runtime. The future operator-override
surface (gated by the deferred `InterlockQuirk` Caution trigger) will
land as a separate Operator-trigger transition slice, never widened
through this Monitor-trigger seam.

## D9-L1 anti-lock posture

Zero severity scalars on this port: no `severity`, no `risk_level`,
no `criticality`, no `sil_level`, no `hazard_level`, no `signal_word`,
no `vendor_status_code` on either the observation envelope or the
scope. Substrate severity codes are flattened by the adapter into the
three-value `EnclosurePermitStatus` codomain before crossing this
seam; severity bookkeeping belongs to the substrate, not the spine.

## Stub roster

`AlwaysPermittedEnclosureObserver` ships inline at the bottom of this
module. It yields one Permitted observation per enclosure in scope
and is the canonical zero-substrate stub for tests and the first-boot
"no observer wired" code path. Mirrors the
`AlwaysQuietCautionLookup` / `AlwaysCoveredClearanceLookup` precedent
shape (inline stub colocated with the port). Production adapters
(EPICS / P4P / Tango) land outside this module under
`cora/enclosure/adapters/` when wired.

## Subscribe shape

`observe` is a plain `def` returning `AsyncIterator[EnclosureObservation]`
directly (no surrounding coroutine). Callers iterate with
`async for observation in observer.observe(scope):`. Connect setup
may happen lazily on the first `__anext__`. Mid-stream disconnect is
the adapter's concern: production adapters re-raise so the runtime
can react; the stub never disconnects.
"""

from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from cora.enclosure.aggregates.enclosure import EnclosurePermitStatus

_STUB_OBSERVED_AT = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class EnclosureObservation:
    """One permit-status reading drained from the substrate.

    `enclosure_code` is the BC-local Enclosure identity surface
    adapters know (the operator-readable code an EPICS PV's record
    name or a Tango device alias maps to). The handler resolves it
    to the `EnclosureId` via the BC's lookup before calling the
    decider.

    `observed_status` is the raw status string the adapter parsed
    from the substrate. The decider parses it against the
    `EnclosurePermitStatus` codomain and raises if the string does
    not match a known status value; substrate values that cannot be
    classified should be flattened to `"Unknown"` by the adapter.

    `observed_at` is the adapter's wall-clock at observation time.
    The handler does NOT override this with the Clock port: the
    substrate's timestamp is more accurate than the handler-side
    clock for monitor-driven facts (the substrate's observation
    moment is the fact-time; the handler's call moment is merely
    when the fact crossed the seam).

    `source_kind` and `source_id` ship as separate strings; the
    handler joins them into the colon-delimited `monitor_ref` wire
    string on the `EnclosurePermitObserved` event payload.
    """

    enclosure_code: str
    observed_status: str
    observed_at: datetime
    source_kind: str
    source_id: str


@dataclass(frozen=True)
class EnclosureObserverScope:
    """Subscription scope: the set of enclosure codes to observe.

    Empty scope is valid and yields no observations (the adapter
    exits the async iterator immediately). The runtime narrows scope
    to the codes the operator has registered; adapters MUST NOT
    silently widen the subscription beyond the supplied scope.
    """

    enclosure_codes: frozenset[str]


@runtime_checkable
class EnclosureObserver(Protocol):
    """Async source of `EnclosureObservation` values from the substrate.

    The substrate adapter (EPICS / P4P / Tango / file-watch) owns
    the subscription lifecycle. The runtime iterates and forwards
    each observation to `observe_enclosure_status` through the
    Enclosure handler bundle.

    Iteration semantics:

      - The iterator is open-ended for live substrates; callers
        either `async for` it for the lifetime of the runtime or
        cancel the task to tear down the subscription.
      - One-shot observers (tests, stubs) MAY exhaust the iterator
        after a finite number of observations and the runtime
        treats `StopAsyncIteration` as a clean teardown.
      - Disconnect handling is the adapter's concern; production
        adapters re-raise substrate disconnect errors through the
        iterator so the runtime can decide whether to retry.
    """

    def observe(self, scope: EnclosureObserverScope) -> AsyncIterator[EnclosureObservation]:
        """Open an observation stream over the supplied scope.

        Returns an `AsyncIterator[EnclosureObservation]` directly
        (no surrounding coroutine). Connect setup may happen lazily
        on the first `__anext__` call.
        """
        ...


class AlwaysPermittedEnclosureObserver:
    """Stub `EnclosureObserver` that yields one Permitted observation per code.

    The canonical zero-substrate observer for tests and the
    first-boot "no observer wired" code path. Mirrors the
    `AlwaysQuietCautionLookup` / `AlwaysCoveredClearanceLookup`
    precedent shape: deterministic, side-effect-free, inline-
    colocated with the port it implements.

    The yielded observation carries:

      - `observed_status="Permitted"` matching
        `EnclosurePermitStatus.PERMITTED`.
      - `observed_at` fixed to `datetime(1970, 1, 1, tzinfo=UTC)` so
        tests can assert exact payloads without injecting a clock
        (deterministic across timezones).
      - `source_kind="Stub"`, `source_id="AlwaysPermittedEnclosureObserver"`
        so the audit trail records the stub-source distinction.

    Production adapters (EPICS subscriber, P4P PVA subscription,
    Tango attribute callback, file-watch tail) ship in
    `cora/enclosure/adapters/` when the runtime is wired to a real
    substrate; this stub is never used outside tests and
    first-boot.
    """

    def observe(self, scope: EnclosureObserverScope) -> AsyncGenerator[EnclosureObservation]:
        return self._drain(scope)

    async def _drain(self, scope: EnclosureObserverScope) -> AsyncGenerator[EnclosureObservation]:
        for enclosure_code in scope.enclosure_codes:
            yield EnclosureObservation(
                enclosure_code=enclosure_code,
                observed_status=EnclosurePermitStatus.PERMITTED.value,
                observed_at=_STUB_OBSERVED_AT,
                source_kind="Stub",
                source_id="AlwaysPermittedEnclosureObserver",
            )


__all__ = [
    "AlwaysPermittedEnclosureObserver",
    "EnclosureObservation",
    "EnclosureObserver",
    "EnclosureObserverScope",
]
