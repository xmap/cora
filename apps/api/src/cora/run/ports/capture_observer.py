"""CaptureObserver port: substrate-driven capture-lifecycle observation stream.

`CaptureObserver` is the BC-local async Protocol a Run-watching runtime
uses to drain capture-lifecycle observations from an external
acquisition tool's substrate (EPICS PV monitors, P4P PVA subscriptions,
Tango attribute callbacks). Substrate details live behind concrete
adapters; the runtime never touches substrate-specific symbols
directly. Mirrors `EnclosureObserver`
([[project_enclosure_stage1_design]] L-port-1 + L-CHARTER-4) at every
layer; the two ports differ only in what they watch.

## BC-local, not promoted to infrastructure/ports

The sole consumer is the Run-watching composition-root runtime. There
is zero cross-BC consumption today: no other BC reads observations off
this port. Promote to `infrastructure/ports/` only on a real second
cross-BC consumer (rule-of-three), exactly the `RunChannelLookup`
precedent.

## Domain vocabulary (substrate-neutral)

- `CapturePhase` (re-exported from `cora.shared.capture_phase`, hoisted
  there because `cora.infrastructure` validates a deployment's declared
  literal table against it and cannot depend on `cora.run.ports`): the
  closed, facility-neutral lifecycle a capture passes through, as CORA
  understands it. NOT the literal vocabulary any one facility's tool
  emits: 2-BM's TomoScan reports free-text values ("Beginning scan",
  "Programming PSO", "Collecting dark fields", "Scan complete") on
  `ScanStatus`, and those strings belong to one tomoscan commit, never
  to this port or the spine. A deployment DECLARES the mapping from its
  own literals to `CapturePhase`; unmapped or unrecognized substrate
  values classify as `UNRECOGNIZED`, never silently as `PROGRESSING` or
  dropped.
- `CaptureObservation`: one capture-lifecycle reading drained from the
  substrate, scoped by `capture_code` (the identity surface the
  runtime's configuration knows, e.g. a named acquisition path). Same
  reach-tier and dual-clock shape as `EnclosureObservation`.
- `CaptureObserverScope`: the set of capture codes the substrate
  adapter should subscribe to. Empty scope is valid and yields no
  observations.

## No terminal claims about a file

A `CapturePhase.ENDED` observation states only that the external tool
reported its lifecycle as finished. It makes NO claim that any file
exists, is complete, or has arrived: 2-BM's own operations reopen the
HDF5 file to append theta AFTER reporting "Scan complete", and the
transfer-status messages mark transfer start, not arrival. Binding an
observed capture to a Dataset is a separate, later, independently-
verified act and is out of scope for this port entirely.

## D6.L2-equivalent anti-lock posture

There is no operator gesture on this port. `CaptureObserver` has no
write half: it is read-only by construction, mirroring the fact that
CORA's `ControlPort` at 2-BM is itself wrapped read-only. Every
observation that crosses this seam represents a substrate reading; the
inbound adapter is responsible for that constraint, exactly as
`EnclosureObserver`'s docstring states for its own seam.

## Subscribe shape

`observe` is a plain `def` returning `AsyncIterator[CaptureObservation]`
directly (no surrounding coroutine), iterated with
`async for observation in observer.observe(scope):`. Connect setup may
happen lazily on the first `__anext__`. Mid-stream disconnect is the
adapter's concern.
"""

from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from cora.shared.capture_phase import CapturePhase
from cora.shared.reach import ReachTier


@dataclass(frozen=True)
class CaptureObservation:
    """One capture-lifecycle reading from the substrate.

    `capture_code` is the identity surface the runtime's configuration
    knows (the deployment-declared name for the acquisition path being
    watched), not a Dataset or file identity.

    `reported_status` is the raw string the adapter read from the
    substrate, or `None` when this observation makes no status claim
    at all (a probe-only re-affirmation read, mirroring
    `EnclosureObservation.observed_status`). `phase` is the same
    reading already classified against `CapturePhase` by the adapter
    using the deployment's declared literal table; carrying both
    lets a consumer log the facility's own words alongside CORA's
    classification of them.

    `reach_tier` states what kind of evidence backed this observation
    (see `ReachTier`); required, not optional, so every adapter states
    its own evidence rather than letting a consumer infer it.

    `observed_at` is the substrate's own time for the observation, and
    is `None` when the substrate supplied none. An adapter with no
    substrate time MUST answer `None` rather than supply its own
    clock: a synthesized time is indistinguishable from a reported one
    once it is written down. Same rule as `EnclosureObservation`.

    `source_kind` and `source_id` are the attribution pair, carried
    unmodified onto any downstream record exactly as the Enclosure
    seam does for `monitor_ref`.
    """

    capture_code: str
    reported_status: str | None
    phase: CapturePhase | None
    reach_tier: ReachTier
    observed_at: datetime | None
    source_kind: str
    source_id: str


@dataclass(frozen=True)
class CaptureObserverScope:
    """Subscription scope: the set of capture codes to observe.

    Empty scope is valid and yields no observations (the adapter exits
    the async iterator immediately).
    """

    capture_codes: frozenset[str]


@runtime_checkable
class CaptureObserver(Protocol):
    """Async source of `CaptureObservation` values from the substrate.

    The substrate adapter owns the subscription lifecycle. A runtime
    iterates and forwards each observation onward; this port makes no
    claim about what the runtime does with what it drains.

    Iteration semantics mirror `EnclosureObserver`: open-ended for live
    substrates, `StopAsyncIteration` is a clean teardown for one-shot
    observers (tests, stubs), and disconnect handling is the adapter's
    concern.
    """

    def observe(self, scope: CaptureObserverScope) -> AsyncIterator[CaptureObservation]:
        """Open an observation stream over the supplied scope.

        Returns an `AsyncIterator[CaptureObservation]` directly (no
        surrounding coroutine). Connect setup may happen lazily on the
        first `__anext__` call.
        """
        ...


class QuietCaptureObserver:
    """Stub `CaptureObserver` that yields nothing.

    The canonical zero-substrate stub for tests and for a deployment
    that has not declared any capture PVs. Mirrors
    `AlwaysPermittedEnclosureObserver`'s role, but yields no
    observations rather than one synthetic reading per code: there is
    no safe "always" value for a capture phase the way there is for a
    permit status, so silence is the honest stub here.
    """

    def observe(self, scope: CaptureObserverScope) -> AsyncGenerator[CaptureObservation]:
        return self._drain(scope)

    async def _drain(self, scope: CaptureObserverScope) -> AsyncGenerator[CaptureObservation]:
        for _ in ():
            yield _


__all__ = [
    "CaptureObservation",
    "CaptureObserver",
    "CaptureObserverScope",
    "CapturePhase",
    "QuietCaptureObserver",
]
