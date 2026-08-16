"""CaptureExperimentIdentityReader: read a witnessed Run's proposal / ESAF /
ESAF-DOI PVs once, at the instant a capture promotes to a Run.

Slice 14a. Mirrors `_capture_baseline_reader.py`'s ONE-READ-NOT-A-FEED
shape exactly: invoked exactly once per promotion by
`RunWitnessRecorder._promote`, right after `record_witnessed_run`
returns a `run_id`, alongside (not instead of) the genesis-baseline
read. There is no buffer, no tick, and no ongoing liveness claim.

## Why the vault, not the event

See `cora.run.aggregates.run.experiment_identity`'s module docstring
for the full argument (memory/project_witnessed_run_prelive_slices.md,
slice 14a). Short version: `RecordWitnessedRun` has no operator behind
it the way `start_run.external_refs` does, so writing these PVs onto
`RunStarted` would be CORA auto-harvesting a re-identifying fact (a
proposal number plus a timestamp, per D0) into an immutable,
INSERT-only event with no way back. `ESAFDOINumber` was checked and
traced to an internal, authenticated APS API
(`EsafApsDbApi.getStationEsafById`, via the upstream `dmagic` source),
not a DOI registration agency; unconfirmed as a genuinely resolvable
public identifier, so it vaults alongside the other two.

## Two traps, both silently recording a WRONG fact rather than failing

1. Every one of these PVs defaults to the substrate literal `"Unknown"`
   when `dmagic` has not populated it. An unpopulated PV therefore
   reads as a plausible string. `resolved_experiment_identity_text` treats
   `"Unknown"`, and an empty string, as ABSENT and returns `None`; the
   caller never writes a literal "Unknown" into the vault.
2. Nothing in the IOC populates these PVs; `dmagic` does, from APS
   scheduling, so a value PERSISTS ACROSS BEAMTIMES until the next
   sync overwrites it. If a value is stale, this reader cannot detect
   that -- there is no freshness heuristic to invent, per the design
   memo's own instruction. Each `*_observed_at` carries the substrate's
   own reading time (`Measurement.produced_at`), the only staleness
   evidence available, so a reader downstream can at least see how old
   a value is. Whether these PVs are reliably synced at 2-BM before a
   beamtime starts is a staff question, not a code question.

## Per-PV failure posture mirrors `_capture_baseline_reader.py`

Every exception is caught and logged, never raised into the caller: a
`ControlPort.read()` failure on one PV drops only that PV's reading and
lets the sweep continue over the rest (mirroring
`capture_watch_preflight.py`'s own per-PV independence), and the vault
write's own failure must never unwind or retry the promotion that
already committed (mirroring `_read_baseline`'s exact posture in
`_run_witness.py`).

Unlike `CaptureBaselineReader`, none of these three values is personal
data, so a write failure's exception text is logged in full (no
`error_class`-only redaction the way `_write_capture_path` requires).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from cora.infrastructure.logging import get_logger
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlValueCoercionError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime
    from uuid import UUID

    from cora.infrastructure.kernel import Kernel
    from cora.operation.ports.control_port import ControlPort, Measurement
    from cora.run.aggregates.run import ExperimentIdentityStore

ROLE_PROPOSAL_NUMBER = "proposal_number"
ROLE_ESAF_NUMBER = "esaf_number"
ROLE_ESAF_DOI_NUMBER = "esaf_doi_number"
"""CORA-owned role keys, matching `Settings.capture_experiment_identity_pvs`'s
closed vocabulary. Module-public (not `_`-prefixed): `capture_watch_preflight`
dispatches its own sweep on these same three keys, so a rename here
cannot silently desync from it."""

_ROLES: tuple[str, ...] = (ROLE_PROPOSAL_NUMBER, ROLE_ESAF_NUMBER, ROLE_ESAF_DOI_NUMBER)

UNKNOWN_EXPERIMENT_IDENTITY_LITERAL = "Unknown"
"""The literal `dmagic` / the IOC leaves an unpopulated experiment-identity
PV reading. Treated as ABSENT, never as a plausible value (Trap 1).
Module-public: `capture_watch_preflight` imports this directly (alongside
`resolved_experiment_identity_text`) so its own decode verdict can distinguish
"substrate's own placeholder" from "genuinely empty" without a second
copy of the literal."""

_log = get_logger(__name__)


def resolved_experiment_identity_text(value: object) -> str | None:
    """Resolve one experiment-identity PV reading to a usable string, or
    `None` when it must be treated as absent.

    `None` for: a non-string reading, an empty (after stripping)
    string, or the substrate's own `"Unknown"` placeholder literal.
    Otherwise the stripped string. Module-public: `capture_watch_preflight`
    imports this directly so its own decode verdict can never drift from
    what this reader actually accepts.
    """
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped == UNKNOWN_EXPERIMENT_IDENTITY_LITERAL:
        return None
    return stripped


class CaptureExperimentIdentityReader:
    """Reads `experiment_identity_pvs[capture_code]`'s three roles once and vaults
    whatever survives.

    `experiment_identity_pvs` is code -> role -> PV, matching
    `Settings.capture_experiment_identity_pvs`. A code with no entry (or
    an empty one) makes `read` a no-op, mirroring `CaptureBaselineReader`'s
    own per-code optionality. A role absent from a code's declared set is
    simply never read; it does not stop the other two.
    """

    def __init__(
        self,
        *,
        deps: Kernel,
        control_port: ControlPort,
        experiment_identity_pvs: Mapping[str, Mapping[str, str]],
        store: ExperimentIdentityStore,
    ) -> None:
        self._deps = deps
        self._control_port = control_port
        self._experiment_identity_pvs = experiment_identity_pvs
        self._store = store

    async def read(self, capture_code: str, run_id: UUID) -> None:
        """Read every role declared for `capture_code` CONCURRENTLY,
        once, and vault whatever survives as one row against `run_id`.

        Concurrent, not sequential: mirrors `CaptureBaselineReader.read`'s
        reasoning exactly -- this runs inline inside
        `RunWitnessRecorder._promote`, on `run_witness_loop`'s single
        consumer path, so a slow or partially-unreachable control system
        must not block the loop from reacting to the next observation.

        Never raises: every failure mode (a dead PV, an unusable
        reading, or the vault write itself) is caught and logged here.
        """
        roles = self._experiment_identity_pvs.get(capture_code)
        if not roles:
            return

        (
            (proposal_number, proposal_number_observed_at),
            (esaf_number, esaf_number_observed_at),
            (esaf_doi_number, esaf_doi_number_observed_at),
        ) = await asyncio.gather(
            *(self._read_one(capture_code, role, roles.get(role)) for role in _ROLES)
        )

        if proposal_number is None and esaf_number is None and esaf_doi_number is None:
            _log.info(
                "capture_experiment_identity.nothing_to_record",
                capture_code=capture_code,
                run_id=str(run_id),
            )
            return

        try:
            await self._store.upsert(
                run_id=run_id,
                proposal_number=proposal_number,
                proposal_number_observed_at=proposal_number_observed_at,
                esaf_number=esaf_number,
                esaf_number_observed_at=esaf_number_observed_at,
                esaf_doi_number=esaf_doi_number,
                esaf_doi_number_observed_at=esaf_doi_number_observed_at,
                created_at=self._deps.clock.now(),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            # Unlike `_write_capture_path`, none of these three values
            # is personal data, so the full exception (which could
            # include the failing row's values in an asyncpg DETAIL
            # line) is safe to log.
            _log.exception(
                "capture_experiment_identity.vault_write_failed",
                capture_code=capture_code,
                run_id=str(run_id),
            )
            return
        _log.info(
            "capture_experiment_identity.recorded",
            capture_code=capture_code,
            run_id=str(run_id),
        )

    async def _read_one(
        self, capture_code: str, role: str, pv: str | None
    ) -> tuple[str | None, datetime | None]:
        """One role's reading, or `(None, None)` when the role is
        undeclared for this code, unreachable, unusable, or resolves to
        `resolved_experiment_identity_text`'s absent case (Trap 1)."""
        if pv is None:
            return None, None
        try:
            reading = await self._control_port.read(pv)
        except asyncio.CancelledError:
            raise
        except (ControlNotConnectedError, ControlTimeoutError, ControlAccessDeniedError) as exc:
            _log.warning(
                "capture_experiment_identity.read_unreachable",
                capture_code=capture_code,
                role=role,
                pv=pv,
                detail=str(exc),
            )
            return None, None
        except ControlValueCoercionError as exc:
            _log.warning(
                "capture_experiment_identity.read_uncoercible",
                capture_code=capture_code,
                role=role,
                pv=pv,
                detail=str(exc),
            )
            return None, None
        except Exception:
            _log.exception(
                "capture_experiment_identity.read_failed",
                capture_code=capture_code,
                role=role,
                pv=pv,
            )
            return None, None
        return self._to_value(capture_code, role, pv, reading)

    def _to_value(
        self, capture_code: str, role: str, pv: str, reading: Measurement
    ) -> tuple[str | None, datetime | None]:
        if reading.produced_at is None:
            # The port's dual-clock rule forbids substituting CORA's own
            # clock for an absent substrate time (Trap 2: there would be
            # no honest staleness evidence to carry).
            _log.info(
                "capture_experiment_identity.no_substrate_time",
                capture_code=capture_code,
                role=role,
                pv=pv,
            )
            return None, None
        value = resolved_experiment_identity_text(reading.value)
        if value is None:
            _log.info(
                "capture_experiment_identity.absent_reading",
                capture_code=capture_code,
                role=role,
                pv=pv,
            )
            return None, None
        return value, reading.produced_at


__all__ = [
    "ROLE_ESAF_DOI_NUMBER",
    "ROLE_ESAF_NUMBER",
    "ROLE_PROPOSAL_NUMBER",
    "UNKNOWN_EXPERIMENT_IDENTITY_LITERAL",
    "CaptureExperimentIdentityReader",
    "resolved_experiment_identity_text",
]
