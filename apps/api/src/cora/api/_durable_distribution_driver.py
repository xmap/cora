"""Acting on a durable-copy verdict: record it, digest it, register it.

The sweep tick. `_durable_distribution_sweep` finds a Dataset whose
durable copy is unrecorded, `_durable_copy_verdict` says what the
probe's answer means, and this walks the consequence.

## Ports are shaped by this consumer, not borrowed whole

Every dependency below is a narrow Protocol declaring only the calls
this module makes, following the `CapturePathLookup` precedent: the
full `CapturePathStore` carries `get` and `get_latest` too, and taking
the whole thing would let a later edit reach for them without anyone
noticing the widening. The one exception is `Clock`, which is imported
from `infrastructure.ports.clock` rather than redeclared: it is already
the narrowest possible port, and a second copy of it would be two
names for one idea.

## The order of writes, and what a crash between them leaves

Recording the location must precede minting, because the locator is
resolved by looking the row up on `(run_id, host, root)`: mint before
write and the locator resolves to nothing. So the order is record,
mint, digest, register, and a crash can land between any two.

An earlier version of this module claimed that was safe by
construction. It was not, and the correction is worth stating plainly
because the false version is the intuitive one:

  - Crash after recording, before registering. The vault row is a TRUE
    statement (the file is there), the Dataset is still a candidate,
    and the next tick redoes the whole thing. The re-record carries the
    same substrate timestamp on the same key, so it states the same
    fact: value-stable, though not write-free, since the upsert's guard
    is `>=` and an equal `observed_at` still refreshes `updated_at`.
    This part was always fine.
  - Crash after registering, or simply the tick after a success.
    Candidacy is NOT read from the write model. It is read from
    `proj_data_distribution_summary`, a projection advanced by
    `infrastructure.projection.worker` on its own asyncio task with
    exponential backoff to 60s. Until that worker catches up, the
    Dataset is still returned as a candidate. Nothing about the
    successful register makes it stop being one.

That second point is why `DurableCopyRegistrar` is REQUIRED to be
idempotent and to establish that from the WRITE model, before it
digests anything. Without it, a stalled projector does not merely
duplicate an event: it re-reads tens of gigabytes over SSH on every
tick, indefinitely. The projection's partial unique index would keep
the READ model correct throughout, which is precisely what makes the
failure invisible while it burns the network.

Stated plainly, because a requirement is not a fix: no implementor of
that Protocol exists yet. Until the composition root builds one, the
obligation above is written down and unmet, and the hole it describes
is open. Whoever wires this is closing it, not inheriting it closed.
The test fake here returns a canned answer and proves nothing about
any real implementation's idempotence.

What this deliberately does NOT do is try to make the digest and the
append atomic. They cannot be: one reads bytes on another host over
SSH, and holding a transaction open across that is worse than the
duplicate it would prevent.

## What stops a tick, and what merely skips a candidate

Only two conditions are systemic, meaning the next candidate would hit
exactly the same wall: a transport that will not carry a request, and
an agent whose grant to register is missing. Everything else is scoped
to one Dataset and must skip, so that one misconfigured Run cannot
wedge the sweep for every other. This mirrors `CaptureScanIngestor`,
where a gate review removed exactly this head-of-line blocking once
already.

## Why the walked set outlives the tick

Skipping within a tick is not enough, and the difference is the whole
reason this state is on the instance rather than the stack. The
candidate query is `ORDER BY created_at ASC LIMIT 1`, so the queue head
is stable, and three of the skip conditions never clear on their own:
a capture code with no durable location, an acquisition folder with no
month in its name, and an ambiguous match. That last one is expected
roughly one month in eight and has no resolution path today. A tick
that forgot what it walked would therefore spend all ten of its
attempts on the first ten permanently-stuck Datasets, forever, and
never reach the eleventh. Ten is not a pathological number here; given
the stated ambiguity rate it is the steady state.

Carrying the set turns that into a cycle: each tick resumes where the
last left off, and when nothing is left the set clears and the sweep
starts over, so a Dataset that was merely waiting gets looked at again.
It also suppresses the re-probe residue described above, since a
Dataset registered this cycle is not re-offered until the cycle ends.

The honest limit: this lives in process memory, so a restart begins a
fresh cycle from the head. That is acceptable because a cycle is cheap
(one directory listing per stuck Dataset) and because the alternative,
persisting a skip list, would need its own erasure story for a table
keyed by Dataset.

## Personal data

The candidate's observed path and the found path both embed a PI
surname. Neither is ever logged: every branch here has an id or a count
that says the same thing, and ids are resolvable through CORA's own
access-controlled read while a log sink cannot be erased. An ambiguous
verdict no longer even carries the colliding paths, so this discipline
is one field shorter than it was; see `_durable_copy_verdict` for why
that field went away rather than being carefully not-logged.

Surfacing which folders collided still needs an authenticated operator
read that does not exist yet. That gap is real and named rather than
closed by putting the paths somewhere convenient.

Refusal text IS logged. That is safe for the `locate` op specifically,
and the scope of that claim matters: every refusal string `locate`,
`_handle` and `run_locate_probe` can produce is a fixed literal, and
`_main`'s catch-all renders the exception TYPE rather than its message,
so a filesystem error cannot carry the filename it failed on.

It is NOT a property of the remote probe as a whole. The `describe` and
`checksum` ops on the same module build their `reason` /
`error_detail` from `str(exc)`, which does embed the path, and their
own SSH adapters log it. That is a real leak, it predates this module,
and nothing here fixes it. Do not read the paragraph above as covering
it, and do not add an op to `locate`'s neighbourhood assuming the
guarantee is ambient.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Protocol

from cora.api._durable_copy_verdict import (
    DurableCopyAmbiguous,
    DurableCopyFound,
    DurableCopyNotYetThere,
    DurableCopyRefused,
    DurableCopyUnreachable,
    read_locate_response,
)
from cora.api._durable_distribution_sweep import months_to_search
from cora.data.adapters.capture_path_locator import mint_capture_path_locator
from cora.infrastructure.logging import get_logger
from cora.shared.storage_root import normalize_storage_root

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from cora.api._durable_distribution_sweep import (
        DurableDistributionCandidate,
        DurableDistributionCandidateLookup,
    )
    from cora.infrastructure.ports.clock import Clock

_log = get_logger(__name__)

_MAX_CANDIDATES_PER_TICK = 10
"""Bound on how many Datasets one tick will walk past before giving up.
Mirrors `CaptureScanIngestor.tick`: without it, a population of stuck
candidates would be re-walked in full on every tick forever."""

_MAX_WALKED_CARRIED = 500
"""Bound on the cycle's memory of what it has already walked. Not a
memory bound: the set is bound into the candidate query as an array, so
this is a bound on how big that query's parameter may get."""


class _Outcome(Enum):
    SUCCESS = auto()
    SKIP = auto()
    STOP_TICK = auto()


@dataclass(frozen=True)
class DurableCopyRegistered:
    """The digest ran and a new Distribution was appended."""

    distribution_id: UUID


@dataclass(frozen=True)
class DurableCopyAlreadyRegistered:
    """Already registered, established from the write model without
    digesting anything. The expected answer while the Distribution
    projection is catching up, and the reason that lag costs a
    directory listing rather than a re-read of the whole file."""

    distribution_id: UUID


@dataclass(frozen=True)
class DurableCopyRegisterRefused:
    """One registration did not happen: the bytes would not read, a
    cross-reference was missing, or the command was rejected. Scoped
    to one Dataset, so the sweep carries on to the next."""

    detail: str
    """Never the path. Same discipline as the probe's refusal text."""


@dataclass(frozen=True)
class DurableCopyRegisterUnauthorized:
    """The registering agent holds no grant for this command. Identical
    for every candidate, so the sweep stops instead of failing the same
    way ten more times."""


DurableCopyRegistration = (
    DurableCopyRegistered
    | DurableCopyAlreadyRegistered
    | DurableCopyRegisterRefused
    | DurableCopyRegisterUnauthorized
)
"""Four members for three outcomes, which is deliberate.

`AlreadyRegistered` and `RegisterRefused` both make the tick move on,
so it is fair to ask why they are separate: one says the work was
already done and the other says it could not be, and a sweep whose logs
cannot tell those apart cannot be diagnosed.

The axis NOT split on is retryable versus permanent, which is the more
tempting one, since `RegisterRefused` covers unreadable bytes (retry
helps) and a missing cross-reference (it does not). That distinction
would matter if permanence starved the queue, and it no longer does:
the walked set rotates past a stuck Dataset rather than re-attempting
it. Split it when something needs to ACT on the difference, not to
record it.
"""


class DurableLocationBinding(Protocol):
    """The one durable location configured for a capture code."""

    @property
    def root(self) -> str: ...
    @property
    def supply_id(self) -> UUID: ...
    @property
    def access_protocol(self) -> str: ...
    @property
    def subdirectory(self) -> str | None: ...


class DurableLocationLookup(Protocol):
    """Which durable location, if any, a capture code binds."""

    def durable_location_for(self, capture_code: str) -> DurableLocationBinding | None: ...


class LocateProbe(Protocol):
    """Ask the host holding the bytes to find the durable copy."""

    async def locate(
        self,
        *,
        root: str,
        months: tuple[str, ...],
        directory_suffix: str,
        filename: str,
        subdirectory: str | None,
    ) -> dict[str, object]: ...


class CapturePathRecorder(Protocol):
    """The one vault call this module makes."""

    async def upsert(
        self,
        *,
        run_id: UUID,
        observed_path: str,
        observed_at: datetime,
        created_at: datetime,
        host: str | None,
        root: str | None,
    ) -> None: ...


class DurableCopyRegistrar(Protocol):
    """Digest the durable copy and register it as a Distribution.

    One call rather than two because the caller has nothing useful to
    do between them: a digest that is not about to be registered is
    wasted work, and splitting them here would put the composition
    root's transaction shape into this module's vocabulary.

    ## Two obligations an implementor MUST meet

    **Idempotent on `(dataset_id, supply_id, locator)`, established
    from the WRITE model.** The caller's candidate list comes from a
    projection that lags, so this method WILL be called again for a
    copy it already registered. Answering `DurableCopyAlreadyRegistered`
    is not an optimization; it is what keeps a stalled projector from
    re-reading the file on every tick forever. Checking the projection
    instead would be no check at all, since that is the same lagging
    source that produced the duplicate call.

    **Check before digesting.** The check is cheap and the digest is
    tens of gigabytes over SSH. An implementation that digests first
    and dedupes afterwards satisfies the letter of idempotence and none
    of its purpose.

    ## Why no principal is passed in

    The identity the register runs as belongs to the implementor, which
    is the composition root that also owns the handler and its
    correlation id. Threading it through here would be pass-through
    with no decision attached. What this module DOES need is the
    authorization OUTCOME, because that alone decides whether to stop
    the tick, and `DurableCopyRegisterUnauthorized` carries it.
    """

    async def register(
        self,
        *,
        dataset_id: UUID,
        supply_id: UUID,
        locator: str,
        durable_path: str,
        access_protocol: str,
    ) -> DurableCopyRegistration: ...


class DurableDistributionDriver:
    """One sweep tick over Datasets whose durable copy is unrecorded."""

    def __init__(
        self,
        *,
        candidate_lookup: DurableDistributionCandidateLookup,
        durable_locations: DurableLocationLookup,
        probe: LocateProbe,
        capture_paths: CapturePathRecorder,
        registrar: DurableCopyRegistrar,
        host: str,
        clock: Clock,
    ) -> None:
        self._candidate_lookup = candidate_lookup
        self._durable_locations = durable_locations
        self._probe = probe
        self._capture_paths = capture_paths
        self._registrar = registrar
        self._host = host
        self._clock = clock
        self._walked: set[UUID] = set()

    async def tick(self) -> None:
        for _ in range(_MAX_CANDIDATES_PER_TICK):
            candidate = await self._candidate_lookup.next_candidate(exclude=frozenset(self._walked))
            if candidate is None:
                # Every candidate has been walked at least once this
                # cycle. Starting over is the only way a Dataset that
                # was merely waiting gets looked at again.
                self._walked.clear()
                return
            outcome = await self._sweep_one(candidate)
            if outcome is _Outcome.STOP_TICK:
                return
            self._walked.add(candidate.dataset_id)
            if outcome is _Outcome.SUCCESS:
                return
            if len(self._walked) >= _MAX_WALKED_CARRIED:
                # More permanently-stuck Datasets than one cycle can
                # carry. Restarting the cycle re-starves whatever sits
                # behind them, so this is deliberately loud: it is a
                # deployment that needs an operator, not a condition the
                # sweep can work around. The fix, if it ever fires, is a
                # `(created_at, dataset_id)` cursor in place of the
                # exclusion list, which is bounded by construction.
                _log.warning(
                    "durable_distribution.walked_set_overflowed",
                    carried=len(self._walked),
                )
                self._walked.clear()
        _log.info("durable_distribution.tick_exhausted_attempts", attempts=_MAX_CANDIDATES_PER_TICK)

    async def _sweep_one(self, candidate: DurableDistributionCandidate) -> _Outcome:
        location = self._durable_locations.durable_location_for(candidate.capture_code)
        if location is None:
            _log.info(
                "durable_distribution.no_durable_location",
                capture_code=candidate.capture_code,
                dataset_id=str(candidate.dataset_id),
            )
            return _Outcome.SKIP

        months = months_to_search(candidate.observed_path, candidate.acquisition_root)
        if not months:
            # The acquisition folder did not open with a YYYY-MM, so
            # there is no month to search and no safe way to widen.
            _log.warning(
                "durable_distribution.no_month_to_search",
                dataset_id=str(candidate.dataset_id),
            )
            return _Outcome.SKIP

        # Normalized once, here, and then used for the probe, the vault
        # key and the locator alike. `resolve` looks the vault row up by
        # this exact string, so a deployment that spelled the root with
        # a trailing slash would otherwise mint an immutable locator
        # that resolves to nothing.
        root = normalize_storage_root(location.root)

        response = await self._probe.locate(
            root=root,
            months=months,
            directory_suffix=candidate.directory_suffix,
            filename=candidate.filename,
            subdirectory=location.subdirectory,
        )
        verdict = read_locate_response(response)

        if isinstance(verdict, DurableCopyNotYetThere):
            # Normal for days after a scan: an operator has not copied
            # the experiment yet. Not a warning, and the Dataset stays
            # a candidate for the next tick.
            _log.info(
                "durable_distribution.not_yet_copied",
                dataset_id=str(candidate.dataset_id),
            )
            return _Outcome.SKIP

        if isinstance(verdict, DurableCopyUnreachable):
            # The hop itself failed, so every remaining candidate would
            # fail the same way. This is one of only two systemic
            # conditions; a refusal of THIS request is not one.
            _log.warning(
                "durable_distribution.probe_unreachable",
                dataset_id=str(candidate.dataset_id),
                detail=verdict.detail,
            )
            return _Outcome.STOP_TICK

        if isinstance(verdict, DurableCopyRefused):
            _log.warning(
                "durable_distribution.probe_refused",
                dataset_id=str(candidate.dataset_id),
                detail=verdict.detail,
            )
            return _Outcome.SKIP

        if isinstance(verdict, DurableCopyAmbiguous):
            # Expected roughly one month in eight, for internal
            # beamtime, whose folders all end in the same `-0`. The
            # paths are deliberately NOT logged: they embed a surname.
            _log.warning(
                "durable_distribution.ambiguous_match",
                dataset_id=str(candidate.dataset_id),
                run_id=str(candidate.run_id),
                match_count=verdict.match_count,
            )
            return _Outcome.SKIP

        return await self._record_and_register(candidate, location, root, verdict)

    async def _record_and_register(
        self,
        candidate: DurableDistributionCandidate,
        location: DurableLocationBinding,
        root: str,
        verdict: DurableCopyFound,
    ) -> _Outcome:
        """Record the location, then register the copy found at it.

        Recording first is required, not stylistic: the locator the
        Distribution carries resolves by looking this row up.
        """
        await self._capture_paths.upsert(
            run_id=candidate.run_id,
            observed_path=verdict.path,
            # The FILE's timestamp, not `clock.now()`. That is what the
            # column means, and it is also what makes the re-record on a
            # retry a true no-op: the upsert is monotonic in
            # `observed_at`, so CORA's clock would write a newer value
            # every time while claiming to state the same fact.
            observed_at=verdict.modified_at,
            created_at=self._clock.now(),
            host=self._host,
            root=root,
        )

        # Minted from the same `root` and `host` just recorded, not from
        # a fresh read of settings: `resolve` looks the row up by
        # exactly these two values, so deriving them twice is how a
        # locator comes to resolve to nothing.
        locator = mint_capture_path_locator(
            observed_path=verdict.path,
            run_id=candidate.run_id,
            host=self._host,
            root=root,
        )
        if locator is None:
            _log.warning(
                "durable_distribution.locator_not_minted",
                dataset_id=str(candidate.dataset_id),
            )
            return _Outcome.SKIP

        registration = await self._registrar.register(
            dataset_id=candidate.dataset_id,
            supply_id=location.supply_id,
            locator=locator,
            durable_path=verdict.path,
            access_protocol=location.access_protocol,
        )

        if isinstance(registration, DurableCopyRegisterUnauthorized):
            _log.warning(
                "durable_distribution.register_unauthorized",
                dataset_id=str(candidate.dataset_id),
            )
            return _Outcome.STOP_TICK

        if isinstance(registration, DurableCopyRegisterRefused):
            # The vault row stays: it is a true statement whether or not
            # the register succeeded, and the Dataset stays a candidate.
            _log.warning(
                "durable_distribution.register_refused",
                dataset_id=str(candidate.dataset_id),
                detail=registration.detail,
            )
            return _Outcome.SKIP

        if isinstance(registration, DurableCopyAlreadyRegistered):
            # The projection has not caught up with a register this
            # sweep already did. SKIP rather than SUCCESS: no work
            # happened, so the tick should spend its turn on a Dataset
            # that still needs one.
            _log.info(
                "durable_distribution.already_registered",
                dataset_id=str(candidate.dataset_id),
                distribution_id=str(registration.distribution_id),
            )
            return _Outcome.SKIP

        _log.info(
            "durable_distribution.registered",
            dataset_id=str(candidate.dataset_id),
            distribution_id=str(registration.distribution_id),
        )
        return _Outcome.SUCCESS


__all__ = [
    "CapturePathRecorder",
    "DurableCopyAlreadyRegistered",
    "DurableCopyRegisterRefused",
    "DurableCopyRegisterUnauthorized",
    "DurableCopyRegistered",
    "DurableCopyRegistrar",
    "DurableCopyRegistration",
    "DurableDistributionDriver",
    "DurableLocationBinding",
    "DurableLocationLookup",
    "LocateProbe",
]
