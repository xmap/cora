"""ExperimentIdentity vault: a witnessed Run's proposal / ESAF / ESAF-DOI.

Mirrors `capture_path.py`'s PATTERN exactly (itself mirroring
`actor_profile` / `ProfileStore`, memory/project_pii_vault): a mutable
side table, keyed by an identity the domain already has (here, the
Run's own `run_id`), holding facts that must never reach an event
payload because events are immutable and INSERT-only at the role level.

A SIBLING table to `run_capture_path`, not a generalization of it,
despite the identical shape: a capture path and a proposal/ESAF number
are different kinds of fact (one is unambiguously personal data by
construction, the other is an institutional identifier that happens to
share this store's write-once-at-promotion timing and PII-vault-shaped
posture for a DIFFERENT reason -- see "Why the vault, not the event"
below). Folding them into one table would make a future, more
permissive disposition on one column read as a disposition on the
other.

## Why this exists

`tomoScan_2BM.template` exposes `ProposalNumber`, `ESAFNumber`, and
`ESAFDOINumber` under `2bmb:TomoScan:`, stamped by `dmagic` from APS
scheduling data, not by the IOC itself. `RunTranslator` has no operator to
ask for a proposal the way `start_run.external_refs` does (see "Why the
vault, not the event"), so a witnessed Run has no experiment identity
at all today. This closes that gap without touching `RunStarted`.

## Why the vault, not the event

`start_run` accepts `external_refs` as an OPERATOR-SUPPLIED command
input (`start_run/command.py`): a human deliberately discloses an
identifier into an append-only, unerasable store. `RecordWitnessedRun`
carries no such field and has no operator behind it; CORA would be
AUTO-HARVESTING these three PVs off an unauthenticated EPICS channel,
every capture, with no human gesture backing the write.
[[project-conjunct-symmetry-design]]'s derivation rule permits exactly
this kind of asymmetry when the missing gesture can be named: here, the
missing gesture is "an operator stamping the proposal", which simply
does not exist on the witnessed path.

D0 (memory/project_witnessed_run_prelive_plan.md) named the concrete
risk: a beamtime proposal number plus a timestamp is a strong join key
against public APS scheduling data, so an auto-harvested proposal
number is re-identifying via auxiliary public data even though the
field names no person. `RunStarted.external_refs` is already
`drop:opaque` in `record_export/_dispositions.py`, so putting these
values on the event would take the unerasability cost and buy no
publishing benefit at all: the decisive asymmetry is that promoting a
value from the vault to the record later is additive and easy, while
retracting one from an immutable event is impossible. The vault is the
choice that does not pre-empt D0.

`ESAFDOINumber` was checked for the one way it could differ: a DOI is
meant to be a public, resolvable, third-party-verifiable handle, which
is the exact kind of thing D0 wants for "a facility can check its own
artifact" without disclosing anything about a person. Tracing
`dmagic`'s own source (`dm.py: get_esaf_doi`) shows the value comes
from `EsafApsDbApi.getStationEsafById`, an INTERNAL, authenticated APS
Data Management API, not a DOI registration agency; a DataCite search
for APS ESAF records returned zero results. Unconfirmed as a genuinely
resolvable public identifier, so it vaults with the other two rather
than riding `external_refs` as its own scheme: per the same asymmetry
argument, guessing "public" and being wrong is unerasable, while
guessing "vault" and being wrong later costs one additive follow-up
slice.

## BC-internal, like CapturePathStore

Same reasoning as `capture_path.py`'s own docstring: exactly one BC
writes and reads this table, so it is built locally in `wire_run(deps)`
and surfaced on `RunHandlers.experiment_identity_store`, never promoted
to a `Kernel` field.

## Three independent facts, three independent substrate times

Unlike `CapturePath` (one PV, one `observed_at`), this row holds THREE
independently-read PVs, each with its own substrate timestamp. Trap:
nothing in the IOC populates any of them; `dmagic` does, from APS
scheduling, so a value PERSISTS ACROSS BEAMTIMES until the next
beamtime's own sync overwrites it. If a value is stale (the current
beamtime's sync has not run yet), CORA cannot detect that from the PV
alone -- `Identifier` (`shared/identifier.py`) is `{scheme, value}` with
no room for a time, which is precisely why this fact lives in a vault
row rather than as an `Identifier` tuple: each `*_observed_at` column
carries the substrate's own reading time (`Measurement.produced_at`),
so a reader can at least SEE how old a value is. No freshness heuristic
is invented here or anywhere in this feature; staleness is a staff
question (memory/project_witnessed_run_prelive_plan.md), not a
computable verdict.

A field may be present while a sibling is absent (e.g. `ProposalNumber`
populated, `ESAFNumber` still reading the substrate's own `"Unknown"`
placeholder): each pair is independently nullable for exactly this
reason.

## Read path never redacts

None of these three values is personal data (institutional identifiers
for a funded experiment, not a person's name or a directory path), so
unlike `CapturePath.observed_path` this dataclass carries no
`repr=False` and no read-path redaction: an operator or the
`get_run` response may show the resolved value directly.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress only at module level for the
# adapter classes. Mirrors `run/aggregates/run/capture_path.py`'s
# identical suppress comment.

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class ExperimentIdentity:
    """One row in the `run_experiment_identity` vault.

    Each of `proposal_number`, `esaf_number`, `esaf_doi_number` is independently
    nullable, paired with its own `*_observed_at` (the substrate's own
    reading time, `Measurement.produced_at`), never CORA's clock: a
    deployment may configure fewer than three roles for a capture code,
    or the substrate may report the `"Unknown"` placeholder / an empty
    string for one PV while another reads a real value.
    """

    run_id: UUID
    proposal_number: str | None
    proposal_number_observed_at: datetime | None
    esaf_number: str | None
    esaf_number_observed_at: datetime | None
    esaf_doi_number: str | None
    esaf_doi_number_observed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExperimentIdentityStore(Protocol):
    """Read / write access to the `run_experiment_identity` table.

    Deliberately no batch/`get_many` read, mirroring `CapturePathStore`:
    every consumer (`get_run`'s route/tool) resolves exactly one `run_id`
    at a time. Two implementors: `PostgresExperimentIdentityStore`
    (production) and `InMemoryExperimentIdentityStore` (tests /
    `app_env=test`).
    """

    async def upsert(
        self,
        *,
        run_id: UUID,
        proposal_number: str | None,
        proposal_number_observed_at: datetime | None,
        esaf_number: str | None,
        esaf_number_observed_at: datetime | None,
        esaf_doi_number: str | None,
        esaf_doi_number_observed_at: datetime | None,
        created_at: datetime,
    ) -> None:
        """Insert a new row or overwrite an existing one for `run_id`.

        Idempotent on the run_id PK: `CaptureExperimentIdentityReader` calls
        this at most once per promotion (one terminal genesis-read per
        Run), but retrying after a partial failure replays cleanly. A
        `None` value overwrites a previously-recorded one on retry: the
        caller always supplies its own full, freshly-read snapshot, not
        a partial patch.
        """
        ...

    async def get(self, run_id: UUID) -> ExperimentIdentity | None:
        """Fetch a row by run_id; `None` when absent (never read, or
        recording disabled)."""
        ...


async def load_run_experiment_identity(
    store: ExperimentIdentityStore, run_id: UUID
) -> ExperimentIdentity | None:
    """Resolve the vaulted experiment identity for a run_id, or `None`.

    Unlike `load_run_capture_path`, no tombstone placeholder: none of
    these three values is personal data, so a plain `None` per field
    (never observed, or the substrate read `"Unknown"`/empty) is honest
    on its own, and the caller already knows the difference between "no
    row" and "not applicable" from whether `capture_code` is set.
    """
    return await store.get(run_id)


_UPSERT_SQL = """
INSERT INTO run_experiment_identity (
    run_id, proposal_number, proposal_number_observed_at,
    esaf_number, esaf_number_observed_at, esaf_doi_number, esaf_doi_number_observed_at,
    created_at, updated_at
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8)
ON CONFLICT (run_id) DO UPDATE
    SET proposal_number = EXCLUDED.proposal_number,
        proposal_number_observed_at = EXCLUDED.proposal_number_observed_at,
        esaf_number = EXCLUDED.esaf_number,
        esaf_number_observed_at = EXCLUDED.esaf_number_observed_at,
        esaf_doi_number = EXCLUDED.esaf_doi_number,
        esaf_doi_number_observed_at = EXCLUDED.esaf_doi_number_observed_at,
        updated_at = now()
"""

_GET_SQL = """
SELECT run_id, proposal_number, proposal_number_observed_at,
       esaf_number, esaf_number_observed_at, esaf_doi_number, esaf_doi_number_observed_at,
       created_at, updated_at
FROM run_experiment_identity
WHERE run_id = $1
"""


def _row_to_experiment_identity(row: asyncpg.Record) -> ExperimentIdentity:
    return ExperimentIdentity(
        run_id=row["run_id"],
        proposal_number=row["proposal_number"],
        proposal_number_observed_at=row["proposal_number_observed_at"],
        esaf_number=row["esaf_number"],
        esaf_number_observed_at=row["esaf_number_observed_at"],
        esaf_doi_number=row["esaf_doi_number"],
        esaf_doi_number_observed_at=row["esaf_doi_number_observed_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresExperimentIdentityStore:
    """asyncpg-backed `ExperimentIdentityStore` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def upsert(
        self,
        *,
        run_id: UUID,
        proposal_number: str | None,
        proposal_number_observed_at: datetime | None,
        esaf_number: str | None,
        esaf_number_observed_at: datetime | None,
        esaf_doi_number: str | None,
        esaf_doi_number_observed_at: datetime | None,
        created_at: datetime,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                _UPSERT_SQL,
                run_id,
                proposal_number,
                proposal_number_observed_at,
                esaf_number,
                esaf_number_observed_at,
                esaf_doi_number,
                esaf_doi_number_observed_at,
                created_at,
            )

    async def get(self, run_id: UUID) -> ExperimentIdentity | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_GET_SQL, run_id)
        return _row_to_experiment_identity(row) if row is not None else None


class InMemoryExperimentIdentityStore:
    """Test / `app_env=test` adapter for `ExperimentIdentityStore`.

    Postgres semantics preserved, mirroring `InMemoryCapturePathStore`:
    on insert, `updated_at = created_at` (the caller's clock read); on
    update, `updated_at = datetime.now(tz=UTC)` (the DB's own clock at
    `ON CONFLICT DO UPDATE` time in the real adapter's `_UPSERT_SQL`,
    never the caller-supplied `created_at`).
    """

    def __init__(self) -> None:
        self._rows: dict[UUID, ExperimentIdentity] = {}

    async def upsert(
        self,
        *,
        run_id: UUID,
        proposal_number: str | None,
        proposal_number_observed_at: datetime | None,
        esaf_number: str | None,
        esaf_number_observed_at: datetime | None,
        esaf_doi_number: str | None,
        esaf_doi_number_observed_at: datetime | None,
        created_at: datetime,
    ) -> None:
        existing = self._rows.get(run_id)
        self._rows[run_id] = ExperimentIdentity(
            run_id=run_id,
            proposal_number=proposal_number,
            proposal_number_observed_at=proposal_number_observed_at,
            esaf_number=esaf_number,
            esaf_number_observed_at=esaf_number_observed_at,
            esaf_doi_number=esaf_doi_number,
            esaf_doi_number_observed_at=esaf_doi_number_observed_at,
            created_at=existing.created_at if existing is not None else created_at,
            updated_at=datetime.now(tz=UTC) if existing is not None else created_at,
        )

    async def get(self, run_id: UUID) -> ExperimentIdentity | None:
        return self._rows.get(run_id)


__all__ = [
    "ExperimentIdentity",
    "ExperimentIdentityStore",
    "InMemoryExperimentIdentityStore",
    "PostgresExperimentIdentityStore",
    "load_run_experiment_identity",
]
