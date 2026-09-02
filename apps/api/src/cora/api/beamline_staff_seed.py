"""The beamline staff seed ceremony: give 2-BM its two real human principals.

`python -m cora.api.beamline_staff_seed` registers, idempotently, the
two real 2-BM beamline staff as CORA `human` Actors under pinned,
deployment-stable ids, so they exist as usable principals for hands-on
testing (register_actor's decider refuses `kind="agent"`; `human` is
the default path this ceremony takes).

## Why a CLI ceremony, not a boot-lifespan hook

`_agent_seed.py` / `_enclosure_seed.py` / `_clearance_template_seed.py`
run automatically on every app boot because an empty or absent config
value makes them a safe no-op everywhere that value is not set. This
seed cannot take that shape: the two people it registers are real, and
their display names are personal data that must never live in this
repository (not in a Settings default, not in a fixture, not in an
env var name baked into the schema of every deployment). The name for
each pinned id has to come from the deploy host at the moment someone
chooses to run this, and a missing name must fail loudly rather than
seed a blank or placeholder, per the PII vault design. Wiring that
requirement into the automatic boot path would mean every OTHER
deployment (dev, CI, test, every other facility) fails to boot unless
it also configures two 2-BM-specific names it has no reason to know.
So this follows `pilot_seed.py`'s shape instead: an explicit, idempotent,
operator-run ceremony, CLI-argument-driven, that reads no descriptor
and touches nothing at import time.

## Where the names come from

Each pinned slot resolves its display name from a CLI flag, defaulting
to a same-named environment variable (`BEAMLINE_STAFF_ADMIN_NAME` /
`BEAMLINE_STAFF_GROUP_MANAGER_NAME` / `BEAMLINE_STAFF_STAFF_NAME`) that
the deploy host sets outside this
repository. Neither name is read into `Settings`: promoting them to the
shared configuration schema would put a 2-BM-specific PII concern in
front of every other deployment's config surface. `_require_all_names_
configured` runs before any database connection is opened, so a missing
name fails immediately and names the unconfigured slot, never the
missing value itself.

The name is written to the `actor_profile` PII vault via
`kernel.profile_store.upsert` (same call `register_actor`'s handler and
`_agent_seed.seed_agent` make) and is NEVER placed in the `ActorRegistered`
event payload, matching the PII vault pattern documented on
`cora.access.aggregates.actor.events.ActorRegistered`.

## Slots are ROLES, not seats

The labels name what a holder is at this facility (`2-bm-admin`,
`2-bm-group-manager`, `2-bm-staff`) rather than an anonymous seat letter.
A role is not personal data, so it is safe in a public repo, and it is
the thing a Policy grant should be read against: `operator-a` tells a
future reader nothing about why that principal may do anything.

What a role does NOT carry today is SCOPE. Policy holds
`(principal, command)` pairs gated by a Conduit and a Surface, with no
beamline dimension, so "manages three beamlines" and "staffs one" are
the same grant here. That costs nothing while CORA runs at one beamline
and becomes real at the second; it is a gap in the Policy model, not
something a slot label can fix, and pretending otherwise by handing the
two roles different COMMANDS would encode a scope difference as a
capability difference and be wrong in a way that is hard to unpick.

## Identity

Three pinned ids, one per role slot, under a namespace distinct from
the seeded-agent range (`01900000-0000-7000-8000-...`): agent ids and
staff-actor ids must never collide, and using a visibly different top
segment plus a different fourth-group nibble (`9000` here vs `8000`
for agents) means a reader can tell which kind of seed minted a given
id without a lookup. Each slot also carries a pinned `event_id` /
`correlation_id` (mirrors `AgentSeedIdentity` in `_agent_seed.py`) so a
re-run derives byte-identical envelopes rather than relying on
`ConcurrencyError` alone to detect the already-seeded case.

## Idempotency

Mirrors `_enclosure_seed.py`'s genesis-append shape: pre-check via
`load_actor`, and on a lost race treat `ConcurrencyError` as
already-seeded. No promotion step exists for Actors (unlike Agents),
so there is nothing to strand: a seeded human Actor is immediately a
usable principal.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final
from uuid import UUID

from cora.access.aggregates.actor import ActorKind, ActorRegistered
from cora.access.aggregates.actor import event_type_name as actor_event_type_name
from cora.access.aggregates.actor import to_payload as actor_to_payload
from cora.access.aggregates.actor.read import load_actor
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_postgres_kernel
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import AllowAllAuthorize, SystemClock, UUIDv7Generator
from cora.infrastructure.ports.event_store import ConcurrencyError
from cora.infrastructure.postgres.pool import create_pool
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from cora.infrastructure.schema_version import verify_schema_version

if TYPE_CHECKING:
    import asyncpg

    from cora.infrastructure.kernel import Kernel

_STREAM_TYPE = "Actor"
_COMMAND_NAME = "SeedBeamlineStaff"

_EXIT_CLEAN = 0
_EXIT_ERROR = 1
_EXIT_SEEDED = 2


class _BeamlineStaffNameMissingError(RuntimeError):
    """Raised when one or more pinned slots have no configured display name.

    The whole point of this error: refuse to seed a blank or
    placeholder name into the PII vault. Its message names the
    unconfigured slot and env var, never a name (there is none to
    name), so the error is safe to print, log, or paste into an issue.
    """


@dataclass(frozen=True)
class BeamlineStaffSlot:
    """One pinned human-actor slot this ceremony seeds.

    `slot` is an anonymous role label (never a real name) used in log
    lines, report output, and as the config key the CLI/env-var lookup
    is keyed on. `env_var` is the environment variable this slot's
    display name defaults from when no CLI flag is given.
    """

    slot: str
    actor_id: UUID
    event_id: UUID
    correlation_id: UUID
    env_var: str
    flag: str
    """The CLI flag this slot's name may be given on directly.

    Carried here rather than derived from `slot`, and rather than
    hand-written next to the parser: the parser and the slot->name map
    are both BUILT from this tuple, so a new slot cannot be added
    without one, and cannot be added with a flag that only reaches one
    of the two places. The previous shape listed every slot three times
    (here, an `add_argument` call, and a dict literal), which is the
    hand-copied-list shape that drops an entry the third time somebody
    edits it."""


#: Distinct from the seeded-agent range (`01900000-0000-7000-8000-...`)
#: by both the top segment and the fourth-group nibble (`9000` vs
#: `8000`), so a human-staff id is visibly not an agent id on sight.
#: Verified against every literal UUID checked into the repo before
#: being picked (see the module docstring's Identity section).
#:
#: The `a` / `b` / `c` nibble is minting order and nothing else. It is
#: deliberately NOT re-lettered when a slot's role label changes: the id
#: IS the person as far as the record is concerned, and every grant made
#: to them hangs off it. Renaming a slot must never mint a new one.
ADMIN_ACTOR_ID: Final[UUID] = UUID("02900000-0000-7000-9000-0000000a0010")
GROUP_MANAGER_ACTOR_ID: Final[UUID] = UUID("02900000-0000-7000-9000-0000000b0010")
STAFF_ACTOR_ID: Final[UUID] = UUID("02900000-0000-7000-9000-0000000c0010")

BEAMLINE_STAFF_SLOTS: Final[tuple[BeamlineStaffSlot, ...]] = (
    BeamlineStaffSlot(
        slot="2-bm-admin",
        actor_id=ADMIN_ACTOR_ID,
        event_id=UUID("02900000-0000-7000-9000-0000000a0012"),
        correlation_id=UUID("02900000-0000-7000-9000-0000000a0014"),
        env_var="BEAMLINE_STAFF_ADMIN_NAME",
        flag="--admin-name",
    ),
    BeamlineStaffSlot(
        slot="2-bm-group-manager",
        actor_id=GROUP_MANAGER_ACTOR_ID,
        event_id=UUID("02900000-0000-7000-9000-0000000b0012"),
        correlation_id=UUID("02900000-0000-7000-9000-0000000b0014"),
        env_var="BEAMLINE_STAFF_GROUP_MANAGER_NAME",
        flag="--group-manager-name",
    ),
    BeamlineStaffSlot(
        slot="2-bm-staff",
        actor_id=STAFF_ACTOR_ID,
        event_id=UUID("02900000-0000-7000-9000-0000000c0012"),
        correlation_id=UUID("02900000-0000-7000-9000-0000000c0014"),
        env_var="BEAMLINE_STAFF_STAFF_NAME",
        flag="--staff-name",
    ),
)


@dataclass
class _Report:
    lines: list[str]
    seeded: bool = False
    failed: bool = False

    def note(self, outcome: str, subject: str, detail: str = "") -> None:
        suffix = f" ({detail})" if detail else ""
        self.lines.append(f"{outcome:<8} {subject}{suffix}")
        if outcome == "seeded":
            self.seeded = True
        if outcome == "error":
            self.failed = True


def _require_all_names_configured(names_by_slot: dict[str, str | None]) -> None:
    """Fail loudly, before any I/O, if any pinned slot has no real name.

    Checked once for the whole slot set (rather than per-slot at write
    time) so a config mistake surfaces immediately, without needing a
    database connection, and names every unconfigured slot in one
    message instead of stopping at the first.
    """
    missing = [
        slot for slot in BEAMLINE_STAFF_SLOTS if not (names_by_slot.get(slot.slot) or "").strip()
    ]
    if not missing:
        return
    remedy = ", ".join(f"{slot.env_var} (slot '{slot.slot}')" for slot in missing)
    raise _BeamlineStaffNameMissingError(
        "refusing to seed a blank or placeholder display name; set the following "
        f"on the deploy host before running this ceremony: {remedy}"
    )


async def _seed_one_beamline_staff_actor(
    kernel: Kernel,
    slot: BeamlineStaffSlot,
    name: str,
    *,
    dry_run: bool,
    report: _Report,
) -> None:
    existing = await load_actor(kernel.event_store, slot.actor_id)
    if existing is not None:
        report.note("exists", f"actor {slot.slot}")
        return
    if dry_run:
        report.note("seeded", f"actor {slot.slot}", "dry-run, not written")
        return

    now = kernel.clock.now()
    event = ActorRegistered(actor_id=slot.actor_id, occurred_at=now, kind=ActorKind.HUMAN)

    # Profile vault upsert FIRST, matching `register_actor`'s own handler
    # and `_agent_seed.seed_agent`: a crash between this and the append
    # below still leaves the name in place for the retry, and no reader
    # can observe the actor_id before its display name exists.
    await kernel.profile_store.upsert(actor_id=slot.actor_id, name=name, created_at=now)

    new_event = to_new_event(
        event_type=actor_event_type_name(event),
        payload=actor_to_payload(event),
        occurred_at=now,
        event_id=slot.event_id,
        command_name=_COMMAND_NAME,
        correlation_id=slot.correlation_id,
        causation_id=None,
        principal_id=SYSTEM_PRINCIPAL_ID,
    )
    try:
        await kernel.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=slot.actor_id,
            expected_version=0,
            events=[new_event],
        )
    except ConcurrencyError:
        report.note("exists", f"actor {slot.slot}", "raced another writer; already present")
        return
    report.note("seeded", f"actor {slot.slot}")


async def seed_beamline_staff(
    *,
    names_by_slot: dict[str, str | None],
    dry_run: bool,
    database_url: str | None = None,
) -> int:
    """Run the ceremony. `database_url` overrides the Settings value so
    the integration tier can point a run at its per-test database; the
    CLI always uses the deployment's own configuration.

    A missing or blank name fails the same way any other ceremony error
    does: caught below, reported as a named line, exit code 1. It is
    still checked before the pool is opened, so a misconfigured run
    never touches the database at all.
    """
    report = _Report(lines=[])
    pool: asyncpg.Pool | None = None
    try:
        _require_all_names_configured(names_by_slot)

        settings = Settings()
        pool = await create_pool(
            database_url if database_url is not None else settings.database_url,
            min_size=1,
            max_size=4,
        )
        await verify_schema_version(pool)
        kernel = make_postgres_kernel(
            pool,
            settings=settings,
            clock=SystemClock(),
            id_generator=UUIDv7Generator(),
            authz=AllowAllAuthorize(),
        )
        for slot in BEAMLINE_STAFF_SLOTS:
            name = names_by_slot[slot.slot]
            assert name is not None and name.strip(), "checked by _require_all_names_configured"
            await _seed_one_beamline_staff_actor(
                kernel, slot, name.strip(), dry_run=dry_run, report=report
            )
        return _finish(report, dry_run)
    except Exception as exc:  # the ceremony is a CLI: name it, exit 1
        report.note("error", "ceremony", str(exc))
        return _finish(report, dry_run)
    finally:
        if pool is not None:
            await pool.close()


def _finish(report: _Report, dry_run: bool) -> int:
    header = "beamline staff seed (dry run)" if dry_run else "beamline staff seed"
    print(header)
    for line in report.lines:
        print(f"  {line}")
    if report.failed:
        return _EXIT_ERROR
    return _EXIT_SEEDED if report.seeded else _EXIT_CLEAN


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface, separate from `main` so tests can pin the
    defaults and flags without touching a database or the environment.

    Each name flag defaults from its matching environment variable so
    the real names never appear as a CLI literal in a shell history
    unless the operator chooses to pass them that way; the deploy
    host's own environment is the intended source.
    """
    parser = argparse.ArgumentParser(
        prog="python -m cora.api.beamline_staff_seed",
        description=(
            "Register 2-BM's named human roles as CORA Actors under "
            "pinned, deployment-stable ids, so they exist as usable principals "
            "for hands-on testing. Display names come from the flags below "
            "(or their matching environment variables) and land only in the "
            "actor_profile PII vault; neither this ceremony nor the repository "
            "ever carries a real name. Idempotent; re-runs report and change "
            "nothing."
        ),
    )
    for member in BEAMLINE_STAFF_SLOTS:
        parser.add_argument(
            member.flag,
            dest=_dest(member),
            default=os.environ.get(member.env_var),
            help=f"Display name for slot '{member.slot}' (default: ${member.env_var}).",
        )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _dest(member: BeamlineStaffSlot) -> str:
    """Argparse destination for a slot's flag, derived once so the parser
    and the reader below cannot disagree about where a value landed."""
    return member.flag.removeprefix("--").replace("-", "_")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    names_by_slot = {member.slot: getattr(args, _dest(member)) for member in BEAMLINE_STAFF_SLOTS}
    return asyncio.run(seed_beamline_staff(names_by_slot=names_by_slot, dry_run=args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
