"""Acting on a durable-copy verdict: record it, digest it, register it.

The sweep tick. `_durable_distribution_sweep` finds a Dataset whose
durable copy is unrecorded, `_durable_copy_verdict` says what the
probe's answer means, and this walks the consequence.

## Ports are shaped by this consumer, not borrowed whole

Every dependency below is a narrow Protocol declaring only the calls
this module makes, following the `CapturePathLookup` precedent: the
full `CapturePathStore` carries `get` and `get_latest` too, and taking
the whole thing would let a later edit reach for them without anyone
noticing the widening.

## The order of writes, and what a crash between them leaves

Recording the location must precede minting, because the locator is
resolved by looking the row up on `(run_id, host, root)`: mint before
write and the locator resolves to nothing. So the order is record,
mint, digest, register, and a crash can land between any two.

That is safe, and by construction rather than by retry luck:

  - Crash after recording, before registering. The vault row is a TRUE
    statement (the file is there), the Dataset is still a candidate
    because candidacy turns on the Distribution and not the vault row,
    and the next tick redoes the whole thing. The re-record is an
    upsert on the same key, so it is a no-op.
  - Crash after registering. The Distribution exists, so the candidate
    query no longer returns this Dataset and nothing repeats.
  - Registration landing twice despite that. The locator is derived
    from `(run_id, host, root, filename)` and is therefore identical on
    a retry, so the projection's partial unique index on
    `(dataset_id, supply_id, uri)` catches it and the writer swallows
    it. The read model stays correct; a duplicate event is the residue.

What this deliberately does NOT do is try to make the digest and the
append atomic. They cannot be: one reads bytes on another host over
SSH, and holding a transaction open across that is worse than the
duplicate it would prevent.

## Personal data

The observed path and the colliding paths in an ambiguous verdict both
embed a PI surname. Neither is ever logged. An ambiguous verdict logs
the ids and the COUNT, which is actionable through CORA's own
access-controlled read and leaks nothing into a sink that cannot be
erased. Surfacing which folders collided needs an authenticated
operator read that does not exist yet; that gap is real and named here
rather than papered over by logging the paths.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Protocol

from cora.api._durable_copy_verdict import (
    DurableCopyAmbiguous,
    DurableCopyFound,
    DurableCopyNotYetThere,
    DurableCopyUnreachable,
    read_locate_response,
)
from cora.api._durable_distribution_sweep import months_to_search
from cora.data.adapters.capture_path_locator import mint_capture_path_locator
from cora.infrastructure.logging import get_logger

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from cora.api._durable_distribution_sweep import (
        DurableDistributionCandidate,
        DurableDistributionCandidateLookup,
    )

_log = get_logger(__name__)

MAX_CANDIDATES_PER_TICK = 10
"""Bound on how many Datasets one tick will walk past before giving up.
Mirrors `CaptureScanIngestor.tick`: without it, a population of stuck
candidates would be re-walked in full on every tick forever."""


class _Outcome(Enum):
    SUCCESS = auto()
    SKIP = auto()
    STOP_TICK = auto()


class Clock(Protocol):
    """The one clock call this module makes."""

    def now(self) -> datetime: ...


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

    Returns the new Distribution id, or `None` when the bytes could not
    be read, which is distinct from a refusal and is the caller's cue
    to leave the Dataset a candidate.
    """

    async def register(
        self,
        *,
        dataset_id: UUID,
        supply_id: UUID,
        locator: str,
        durable_path: str,
        access_protocol: str,
    ) -> UUID | None: ...


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

    async def tick(self) -> None:
        excluded: set[UUID] = set()
        for _ in range(MAX_CANDIDATES_PER_TICK):
            candidate = await self._candidate_lookup.next_candidate(exclude=frozenset(excluded))
            if candidate is None:
                return
            outcome = await self._sweep_one(candidate)
            if outcome is _Outcome.STOP_TICK:
                return
            if outcome is _Outcome.SUCCESS:
                return
            excluded.add(candidate.dataset_id)
        _log.info("durable_distribution.tick_exhausted_attempts", attempts=MAX_CANDIDATES_PER_TICK)

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

        response = await self._probe.locate(
            root=location.root,
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
            # The probe could not look. Stop the tick rather than walk
            # every remaining candidate into the same dead transport.
            _log.warning(
                "durable_distribution.probe_unreachable",
                dataset_id=str(candidate.dataset_id),
                detail=verdict.detail,
            )
            return _Outcome.STOP_TICK

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

        return await self._record_and_register(candidate, location, verdict)

    async def _record_and_register(
        self,
        candidate: DurableDistributionCandidate,
        location: DurableLocationBinding,
        verdict: DurableCopyFound,
    ) -> _Outcome:
        """Record the location, then register the copy found at it.

        Recording first is required, not stylistic: the locator the
        Distribution carries resolves by looking this row up.
        """
        observed_at = self._clock.now()
        await self._capture_paths.upsert(
            run_id=candidate.run_id,
            observed_path=verdict.path,
            observed_at=observed_at,
            created_at=observed_at,
            host=self._host,
            root=location.root,
        )

        # Minted from the location just recorded, not from a fresh
        # read of settings: `resolve` looks the row up by exactly these
        # two values, so deriving them twice is how a locator comes to
        # resolve to nothing.
        locator = mint_capture_path_locator(
            observed_path=verdict.path,
            run_id=candidate.run_id,
            host=self._host,
            root=location.root,
        )
        if locator is None:
            _log.warning(
                "durable_distribution.locator_not_minted",
                dataset_id=str(candidate.dataset_id),
            )
            return _Outcome.SKIP

        distribution_id = await self._registrar.register(
            dataset_id=candidate.dataset_id,
            supply_id=location.supply_id,
            locator=locator,
            durable_path=verdict.path,
            access_protocol=location.access_protocol,
        )
        if distribution_id is None:
            # The bytes could not be read or the register was refused.
            # The vault row stays: it is a true statement either way,
            # and the Dataset stays a candidate for the next tick.
            _log.warning(
                "durable_distribution.register_failed",
                dataset_id=str(candidate.dataset_id),
            )
            return _Outcome.SKIP

        _log.info(
            "durable_distribution.registered",
            dataset_id=str(candidate.dataset_id),
            distribution_id=str(distribution_id),
        )
        return _Outcome.SUCCESS


__all__ = [
    "MAX_CANDIDATES_PER_TICK",
    "CapturePathRecorder",
    "Clock",
    "DurableCopyRegistrar",
    "DurableDistributionDriver",
    "DurableLocationBinding",
    "DurableLocationLookup",
    "LocateProbe",
]
