"""CaptureObserver port: substrate-driven capture-lifecycle observation stream.

`CaptureObserver` is the BC-local async Protocol a Run-watching runtime
uses to drain capture readings from an external acquisition tool's
substrate (EPICS PV monitors, P4P PVA subscriptions, Tango attribute
callbacks). Substrate details live behind concrete adapters; the
runtime never touches substrate-specific symbols directly. Mirrors
`EnclosureObserver` ([[project_enclosure_stage1_design]] L-port-1 +
L-CHARTER-4) at every layer; the two ports differ only in what they
watch.

## BC-local, not promoted to infrastructure/ports

The sole consumer is the Run-watching composition-root runtime. There
is zero cross-BC consumption today: no other BC reads observations off
this port. Promote to `infrastructure/ports/` only on a real second
cross-BC consumer (rule-of-three), exactly the `RunChannelLookup`
precedent.

## Four reading kinds, one stream

`observe()` yields `AnyCaptureObservation`, the union of
`CaptureLifecycleObservation` (a phase claim: BEGUN / PROGRESSING /
ENDED / ABORTED / UNRECOGNIZED, or no claim at all on a probe-only or
disconnect reading), `CaptureProgressObservation` (a numeric
progress counter, e.g. `ImagesSaved`), `CapturePreconditionBypassObservation`
(the optional `testing` role's tri-state reading, slice 11), and
`CapturePathObservation` (the optional `full_file_name` role's text
reading, slice 13). A consumer narrows with `isinstance`.
The four are peers, not a supertype and subtypes: a single reading is
never more than one of these at once, so one closed-over
`CaptureObservation` name for "the default kind" would have made an
isinstance check on the lifecycle kind read as a supertype check
rather than the kind check it actually is. Kept distinct instead, per
R2/R4 (naming review, slice 10).

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
- `CaptureLifecycleObservation`: one capture-lifecycle reading drained
  from the substrate, scoped by `capture_code` (the identity surface
  the runtime's configuration knows, e.g. a named acquisition path).
  Same reach-tier and dual-clock shape as `EnclosureObservation`.
- `CaptureProgressObservation`: one numeric progress reading (a
  monotonic counter such as images saved or collected) drained from a
  role the deployment declared under the same capture code. `role` is
  the CORA-owned role key (`images_saved`, `images_collected`), the
  same closed vocabulary `status` and `abort` already use; it is
  deliberately not named `channel_name`, which is a different, operator-
  authored identifier on the Run BC's `AppendObservations` write path
  (`cora.run.aggregates.run.state.ChannelName`) that this reading does
  not carry directly. A consumer that writes this value onward as an
  observation entry chooses its own `channel_name` at that boundary.
- `CapturePreconditionBypassObservation`: one reading of the optional
  `testing` role (slice 11), drained from a role the deployment
  declared under the same capture code, same closed vocabulary as
  `status` / `abort` / the progress roles. The type and field names are
  facility-neutral (`beam_preconditions_bypassed`), NOT the substrate's
  own `testing` word, mirroring `CaptureProgressSnapshot`'s own
  precedent of keeping this domain vocabulary substrate-neutral even
  where the CONFIG-facing role key mirrors the PV name. Tri-state, not
  a phase claim and not a progress counter:
  `beam_preconditions_bypassed=True` is a positive claim the substrate
  is bypassing its own beam preconditions for this capture, `=False` is
  a positive claim it is NOT (a real acquisition), and `=None` means
  the reading did not decode or none has ever arrived. NOT
  `Observation.is_simulated`: that column answers whether the NUMBERS
  CORA recorded were invented (a simulator or replay feeder), an
  orthogonal question from whether the facility had beam. See
  [[project_run_witness_test_provenance_slice11]] for the full
  argument against collapsing the two.
- `CapturePathObservation` (slice 13): one reading of the optional
  `full_file_name` role, the areaDetector file plugin's own filename
  readback (`FullFileName_RBV`), drained continuously and independently
  of any one capture (the file plugin fires this at file OPEN, which
  can land before, during, or after any particular capture's own BEGUN
  observation reaches this port). **`observed_path` is personal data**:
  2-BM's directory layout embeds `{UserLastName}-{ProposalNumber}`
  (`tomoscan_2bm.py:474-477`), so every real reading of this role
  carries a person's surname. A consumer of this observation MUST NOT
  log it, put it on an event, or persist it anywhere but the dedicated
  `run_capture_path` PII vault (`CapturePathStore`, mirroring
  `actor_profile` / `ProfileStore`). Recording an observed path is
  NOT a claim the file is complete, so it does not violate "No terminal
  claims about a file" below; it says only that the file plugin opened
  a file at this substrate time, nothing about what it contains or
  whether writing to it has finished.
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
verified act and is out of scope for this port entirely. Same rule for
`CaptureProgressObservation`: a progress count is not a claim about
what a file on disk contains, and `commanded_total` is not a claim
that the capture will, or did, reach it.

## D6.L2-equivalent anti-lock posture

There is no operator gesture on this port. `CaptureObserver` has no
write half: it is read-only by construction, mirroring the fact that
CORA's `ControlPort` at 2-BM is itself wrapped read-only. Every
observation that crosses this seam represents a substrate reading; the
inbound adapter is responsible for that constraint, exactly as
`EnclosureObserver`'s docstring states for its own seam.

## Subscribe shape

`observe` is a plain `def` returning `AsyncIterator[AnyCaptureObservation]`
directly (no surrounding coroutine), iterated with
`async for observation in observer.observe(scope):`. Connect setup may
happen lazily on the first `__anext__`. Mid-stream disconnect is the
adapter's concern.
"""

from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from cora.shared.capture_phase import CapturePhase
from cora.shared.reach import ReachTier


@dataclass(frozen=True)
class CaptureLifecycleObservation:
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
class CaptureProgressObservation:
    """One numeric progress reading from the substrate.

    Not a phase claim: a progress role (`images_saved`,
    `images_collected`) reports how far a capture has gotten, never
    whether it began, ended, or was aborted. `role` is the CORA-owned
    role key the deployment declared this PV under in
    `Settings.capture_watch_pvs` (the same closed vocabulary `status`
    and `abort` already use), NOT the Run BC's operator-authored
    `ChannelName`.

    `value` is the decoded numeric reading. An adapter that cannot
    decode a reading as a finite number emits nothing for it rather
    than guessing; see `_capture_observer.py`.

    `commanded_total` is the substrate's own target count for this role
    when the reading carries one (2-BM's `"<reached>/<commanded>"`
    stringout format), or `None` when the reading has no such second
    half. It is NOT a completeness signal: `wait_camera_done()`'s poll
    loop returns on `CamAcquireBusy == 0` before a final
    `update_status()` call, so `value < commanded_total` is the normal
    terminal state of a successful scan, not evidence of a shortfall.
    Carried because a witnessed terminal needs the substrate's own
    target as evidence, never because `value == commanded_total` is a
    valid test; see `_capture_observer.py` and
    `CaptureProgressSnapshot`.

    `reach_tier`, `observed_at`, `source_kind`, `source_id` carry the
    same meaning as on `CaptureLifecycleObservation`.
    """

    capture_code: str
    role: str
    value: float
    commanded_total: float | None
    reach_tier: ReachTier
    observed_at: datetime | None
    source_kind: str
    source_id: str


@dataclass(frozen=True)
class CapturePreconditionBypassObservation:
    """One reading of the optional `testing` role: whether the substrate
    is bypassing its own beam preconditions for this capture code.

    Named for the domain fact, not the substrate's own `testing` word
    (which stays confined to the `Settings.capture_watch_pvs` role key
    and `_capture_observer.py`), mirroring `CaptureProgressSnapshot`'s
    own precedent of keeping this domain vocabulary facility-neutral.

    `beam_preconditions_bypassed` is the decoded tri-state claim, via
    `binary_code` (`_capture_observer.py`) applied to the raw reading:
    `True` (asserted) is a positive claim the substrate is bypassing
    its beam preconditions for this capture; `False` (clear) is a
    positive claim it is NOT, i.e. a real acquisition; `None` means the
    reading did not decode. Three states, not two: `None` must never
    collapse into `False`, since "unknown" and "confirmed real" are
    different claims a reader needs to tell apart.

    `role` is not carried (unlike `CaptureProgressObservation`): the
    `testing` role is singular per capture code, so there is nothing
    to disambiguate between multiple readings of this kind.

    `reach_tier`, `observed_at`, `source_kind`, `source_id` carry the
    same meaning as on `CaptureLifecycleObservation`. `observed_at` is
    the substrate's OWN time for this reading, never CORA's clock: the
    role is read continuously and independently of any one capture, so
    a consumer retaining the latest reading needs this to tell a fresh
    reading from a stale one still standing from hours earlier.
    """

    capture_code: str
    beam_preconditions_bypassed: bool | None
    reach_tier: ReachTier
    observed_at: datetime | None
    source_kind: str
    source_id: str


@dataclass(frozen=True)
class CapturePathObservation:
    """One reading of the optional `full_file_name` role: the
    areaDetector file plugin's own filename readback (`FullFileName_RBV`).

    `observed_path` is PERSONAL DATA (see this module's docstring,
    "Domain vocabulary" bullet on this class). It MUST NOT be logged,
    placed on an event payload, or persisted anywhere but the
    `run_capture_path` PII vault. A consumer that retains this
    observation (e.g. to compare against a Run's own BEGUN time before
    writing it to the vault) must audit every log line it emits along
    that path for this field.

    Not a phase claim, not a numeric counter, not a tri-state flag: a
    plain text reading, the substrate's file plugin's own string, taken
    as-is once it passes the length/emptiness checks in
    `_capture_observer.py` (see `_from_full_file_name_reading`).

    `role` is not carried (mirrors `CapturePreconditionBypassObservation`):
    `full_file_name` is singular per capture code.

    `reach_tier`, `observed_at`, `source_kind`, `source_id` carry the
    same meaning as on `CaptureLifecycleObservation`. `observed_at` is
    the substrate's OWN time for this reading, never CORA's clock: it
    is the timestamp a consumer compares against a Run's own BEGUN time
    to decide whether this reading belongs to that Run at all (Finding
    A, memory/project_witnessed_run_prelive_slices.md slice 13): a
    reading whose file plugin fired before this capture even started
    almost certainly describes the PREVIOUS capture's file.
    """

    capture_code: str
    observed_path: str = field(repr=False)
    """Personal data. `repr=False` so an accidental bare `_log.info(...,
    observation=observation)` or assertion-failure message renders this
    dataclass without it; deliberate defense-in-depth, not the primary
    guard (nothing should be logging this observation at all)."""
    reach_tier: ReachTier
    observed_at: datetime | None
    source_kind: str
    source_id: str


AnyCaptureObservation = (
    CaptureLifecycleObservation
    | CaptureProgressObservation
    | CapturePreconditionBypassObservation
    | CapturePathObservation
)
"""The union `observe()` yields. Named explicitly rather than reusing
any one member's name for the union, so a caller that has not yet been
updated to narrow by `isinstance` fails type-check instead of silently
treating one observation kind as another."""


@dataclass(frozen=True)
class CaptureObserverScope:
    """Subscription scope: the set of capture codes to observe.

    Empty scope is valid and yields no observations (the adapter exits
    the async iterator immediately).
    """

    capture_codes: frozenset[str]


@runtime_checkable
class CaptureObserver(Protocol):
    """Async source of `AnyCaptureObservation` values from the substrate.

    The substrate adapter owns the subscription lifecycle. A runtime
    iterates and forwards each observation onward; this port makes no
    claim about what the runtime does with what it drains.

    Iteration semantics mirror `EnclosureObserver`: open-ended for live
    substrates, `StopAsyncIteration` is a clean teardown for one-shot
    observers (tests, stubs), and disconnect handling is the adapter's
    concern.
    """

    def observe(self, scope: CaptureObserverScope) -> AsyncIterator[AnyCaptureObservation]:
        """Open an observation stream over the supplied scope.

        Returns an `AsyncIterator[AnyCaptureObservation]` directly (no
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

    def observe(self, scope: CaptureObserverScope) -> AsyncGenerator[AnyCaptureObservation]:
        return self._drain(scope)

    async def _drain(self, scope: CaptureObserverScope) -> AsyncGenerator[AnyCaptureObservation]:
        for _ in ():
            yield _


__all__ = [
    "AnyCaptureObservation",
    "CaptureLifecycleObservation",
    "CaptureObserver",
    "CaptureObserverScope",
    "CapturePathObservation",
    "CapturePhase",
    "CapturePreconditionBypassObservation",
    "CaptureProgressObservation",
    "QuietCaptureObserver",
]
