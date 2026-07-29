"""Execute a real Postgres point-in-time restore and verify the event store.

Run from the repo root:  python scripts/restore_drill.py

## What this proves, and why it is not a unit test

A backup nobody has restored is a belief. This script destroys a real
cluster and brings it back, so the claim "CORA's event store is
recoverable" rests on an execution rather than on a configuration file
that looks correct.

It verifies at the DOMAIN level, which event sourcing makes possible in a
way most systems are not. "Postgres started" says nothing about whether
the record survived. So the drill seeds three known Run streams and, for
the two that should come back, hashes each one's ordered fold and asserts
the digest is unchanged across the restore. A restore that silently
reordered or dropped an event inside a stream would pass a row count and
fail here. The third stream is checked for ABSENCE, so it has no digest
to compare.

## The shape of the drill, and why each phase exists

    Run A  ->  full backup  ->  Run B  ->  [target time T]  ->  Run C

Run A is in the base backup. Run B is written AFTER it, so nothing but
replayed WAL can bring Run B back: it is what separates a working archive
from a working backup. Run C is written after T and must NOT return,
which is what separates point-in-time recovery from restore. A `pg_dump`
strategy passes the Run A check and fails both of the others, which is
why the row this closed could not be answered with one. See the tool
comparison in the Recovery section of docs/stack/deployment.md.

Those three streams carry the result. The remaining checks (schema
revision, commit order) confirm the restore did not disturb things it
should not have; neither can fail in a state this drill constructs, so
read them as regression guards rather than as evidence for the headline
claim.

Every external command is echoed before it runs, except inside poll
loops, which would otherwise print the same query eighty times. The
echoed commands are the runbook in docs/stack/deployment.md; if the two
ever disagree, this file is the one that was executed.

## Isolation

The drill stack (infra/backup/docker-compose.backup.yml) is separate from
the dev database and binds port 5433, overridable with CORA_DRILL_PORT.
This script deletes the contents of its PGDATA.

The invariant that matters is about VOLUMES, not ports: the destructive
step runs in a container whose only mounts are the two drill volumes, so
no host path and no other project's volume is reachable from it. The
published port is only how the drill talks to its own cluster, and it
refuses 5432 so that nothing else on the machine is pointed at a database
this script is about to delete.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = REPO_ROOT / "infra" / "backup" / "docker-compose.backup.yml"
ATLAS_DIR = REPO_ROOT / "infra" / "atlas"

# Overridable so an unrelated container already holding 5433 is not a
# reason the drill goes unrun. The compose file reads the same variable.
DRILL_PORT = os.environ.get("CORA_DRILL_PORT", "5433")
DRILL_DSN = f"postgres://cora:cora@localhost:{DRILL_PORT}/cora"
ATLAS_URL = f"{DRILL_DSN}?sslmode=disable"

# Pinned rather than left to the compose file's `name:` key, which
# COMPOSE_PROJECT_NAME in the environment silently overrides. Under
# `COMPOSE_PROJECT_NAME=infra` the drill's `down -v` would resolve service
# `postgres` to the DEV container and remove it. The dev VOLUME survives
# (down -v only removes volumes declared in the file it was passed), but
# the container should not be collateral either.
COMPOSE_PROJECT = "cora-backup-drill"

PGDATA = "/var/lib/postgresql/18/docker"
STANZA = "cora"

# Fixed ids so a failure names a stream an operator can go look at.
RUN_A = "0a000000-0000-0000-0000-00000000000a"
RUN_B = "0b000000-0000-0000-0000-00000000000b"
RUN_C = "0c000000-0000-0000-0000-00000000000c"

# Real CORA Run event types (cora.run.aggregates.run.events), in a
# lifecycle order the evolver would actually produce. Using the real
# names keeps this a CORA stream rather than a synthetic one.
RUN_A_EVENTS = [
    "RunStarted",
    "RunObservationLogbookOpened",
    "RunHeld",
    "RunResumed",
    "RunCompleted",
]
RUN_B_EVENTS = ["RunStarted", "RunObservationLogbookOpened", "RunCompleted"]
RUN_C_EVENTS = ["RunStarted", "RunAborted"]


class DrillError(RuntimeError):
    """A drill phase failed. The message names the phase."""


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
    quiet: bool = False,
) -> str:
    """Echo a command, run it, return stdout. Raise on a non-zero exit.

    `quiet` suppresses the echo for poll loops, where printing the same
    query eighty times buries the phases the reader came for.
    """
    prefix = "".join(f"{k}={v} " for k, v in (extra_env or {}).items())
    shown = f"{prefix}{shlex.join(cmd)}"
    if not quiet:
        print(f"    $ {shown}", flush=True)
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=({**os.environ, **extra_env} if extra_env else None),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise DrillError(
            f"command failed (exit {result.returncode}): {shown}\n"
            f"stdout: {result.stdout.strip()}\n"
            f"stderr: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def compose(*args: str) -> str:
    return run(["docker", "compose", "-p", COMPOSE_PROJECT, "-f", str(COMPOSE_FILE), *args])


def pgbackrest_live(*args: str) -> str:
    """A pgBackRest command that needs a RUNNING cluster.

    `stanza-create`, `check` and `backup` all connect to Postgres (to read
    control data and to call pg_backup_start / pg_backup_stop), so they
    run inside the Postgres container where the unix socket is. On a VM or
    a workstation there is no split: pgBackRest is installed alongside
    Postgres and every command below is the same command without the
    `docker compose exec` prefix.
    """
    return compose(
        "exec", "-T", "-u", "postgres", "postgres", "pgbackrest", f"--stanza={STANZA}", *args
    )


def pgbackrest_offline(*args: str) -> str:
    """A pgBackRest command that runs while the cluster is STOPPED.

    `restore` writes into PGDATA and must not run against a live cluster,
    so it uses the one-shot tool container, which mounts the same volumes
    and needs no database connection.
    """
    return compose("run", "--rm", "pgbackrest", f"--stanza={STANZA}", *args)


def sql(query: str, *, quiet: bool = False) -> str:
    """Run one statement against the drill database, return a bare scalar."""
    return run(["psql", DRILL_DSN, "-tAqc", query], quiet=quiet)


def wait_for(predicate, *, what: str, timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except DrillError:
            pass
        time.sleep(1.0)
    raise DrillError(f"timed out after {timeout:.0f}s waiting for {what}")


def phase(number: int, title: str) -> None:
    print(f"\n[{number}] {title}", flush=True)


def seed_run(run_id: str, event_types: list[str]) -> None:
    """Append one Run stream, one event per version, in a single transaction."""
    values = ",\n    ".join(
        f"(gen_random_uuid(), 'Run', '{run_id}'::uuid, {version}, '{event_type}', "
        f"jsonb_build_object('run_id', '{run_id}', 'seq', {version}), "
        f"gen_random_uuid(), now())"
        for version, event_type in enumerate(event_types, start=1)
    )
    sql(
        "INSERT INTO events (event_id, stream_type, stream_id, version, "
        "event_type, payload, correlation_id, occurred_at) VALUES\n    "
        f"{values};"
    )


def stream_digest(run_id: str) -> str:
    """Hash a stream's ordered fold: the replay input, not just its rows.

    Folding order is `version`, the same order the evolver reads. A restore
    that dropped, duplicated or reordered an event changes this digest even
    when the row count is unchanged.
    """
    return sql(
        "SELECT coalesce(md5(string_agg("
        "version || '|' || event_type || '|' || payload::text, E'\\n' "
        "ORDER BY version)), 'EMPTY') "
        f"FROM events WHERE stream_type = 'Run' AND stream_id = '{run_id}'::uuid;"
    )


def stream_event_types(run_id: str) -> list[str]:
    raw = sql(
        "SELECT coalesce(string_agg(event_type, ',' ORDER BY version), '') "
        f"FROM events WHERE stream_type = 'Run' AND stream_id = '{run_id}'::uuid;"
    )
    return [part for part in raw.split(",") if part]


def commit_order_violations(run_id: str) -> int:
    """Count places where global commit order disagrees with stream version.

    `position` is the secondary key of the projection cursor. The canonical
    key is the `(transaction_id, position)` tuple, because position alone
    is unsafe: see the module docstring of
    cora.infrastructure.ports.event_store. Position still has to come back
    in step with `version`, so this is worth asserting, but a physical
    restore replays stored column values as they were and cannot permute
    them. Read this as a regression guard, not as evidence the restore
    worked.
    """
    return int(
        sql(
            "SELECT count(*) FROM (SELECT position, "
            "lag(position) OVER (ORDER BY version) AS prev "
            f"FROM events WHERE stream_type = 'Run' AND stream_id = '{run_id}'::uuid"
            ") t WHERE prev IS NOT NULL AND position <= prev;"
        )
    )


def schema_revision() -> str:
    """The Atlas revision the database currently sits at.

    Migrations are applied OUT OF BAND by a Go binary that is not a Python
    dependency (`make migrate-apply`), and nothing asserts the schema
    version at boot, so a restore that lands an older cluster under a newer
    image fails silently rather than loudly.

    Scope this honestly: the drill migrates BEFORE it backs up, so every
    recovery target here sits after every migration and this check cannot
    fail in a state the drill constructs. It confirms the schema came back
    with the data; it does not exercise the stale-schema scenario. The
    operator-facing guard for that is `make migrate-status` after a
    restore, in docs/stack/deployment.md.
    """
    return sql(
        "SELECT coalesce(max(version), 'NONE') FROM atlas_schema_revisions.atlas_schema_revisions;"
    )


def postgres_accepting_connections() -> bool:
    return sql("SELECT 1;", quiet=True) == "1"


def recovery_finished() -> bool:
    return sql("SELECT pg_is_in_recovery();", quiet=True) == "f"


def archiving_healthy() -> bool:
    """True when the most recent archive attempt succeeded.

    Deliberately NOT `failed_count = 0`. Postgres starts archiving the
    moment it boots with archive_mode=on, which is BEFORE the stanza
    exists, so a correct setup always records a burst of early
    FileMissingError failures against archive.info. Treating a nonzero
    lifetime failure count as unhealthy would make a working archive look
    broken forever. What matters is whether archiving is working NOW, so
    the check compares the last success against the last failure.
    """
    verdict = sql(
        "SELECT last_archived_time IS NOT NULL AND "
        "(last_failed_time IS NULL OR last_archived_time > last_failed_time) "
        "FROM pg_stat_archiver;",
        quiet=True,
    )
    return verdict == "t"


def archived_through(segment: str) -> bool:
    """True once the repository holds `segment` or a later one.

    Waiting on `archiving_healthy` instead would return immediately, since
    the full backup's pg_backup_stop already archived a segment and left
    the archiver looking healthy. The drill has to wait for the SPECIFIC
    segment it just closed, or the assertion that follows races the
    archiver and fails a working setup.

    WAL filenames are fixed-width hex, so a lexicographic comparison is an
    ordering comparison. `last_archived_wal` can also hold a `.backup`
    label filename, which sorts after the segment it belongs to and so
    cannot satisfy this check early.
    """
    latest = sql("SELECT coalesce(last_archived_wal, '') FROM pg_stat_archiver;", quiet=True)
    return latest >= segment and not latest.endswith(".backup")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep",
        action="store_true",
        help="leave the drill stack running afterwards for inspection",
    )
    args = parser.parse_args()

    print("CORA restore drill: Postgres point-in-time recovery")
    print(f"repo:  {REPO_ROOT}")
    print(f"stack: {COMPOSE_FILE.relative_to(REPO_ROOT)} (port {DRILL_PORT})")

    # The drill destroys its own volume, never the dev one, so 5432 is not
    # a data-loss risk. It is a CONFUSION risk: for the minutes the drill
    # runs, localhost:5432 would be the drill database, which is exactly
    # where LOCAL_DB_URL and `make dev` point. Anything attaching there
    # would land on a cluster this script is about to delete.
    if DRILL_PORT == "5432":
        print(
            "CORA_DRILL_PORT=5432 is the dev database's port. Pick another;\n"
            "the drill publishes its own throwaway cluster there.",
            file=sys.stderr,
        )
        return 2

    # Catch broadly. A missing docker/psql/atlas raises FileNotFoundError
    # and Ctrl-C raises KeyboardInterrupt; both would otherwise print a
    # traceback and skip the cleanup hint, at the moment the operator most
    # needs it, having just been left with a half-restored cluster running.
    try:
        execute_drill()
    except (DrillError, OSError, ValueError, IndexError, KeyboardInterrupt) as exc:
        label = "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "DRILL FAILED"
        print(f"\n{label}: {exc or type(exc).__name__}", file=sys.stderr)
        print(
            "\nThe stack is left running so the failure can be inspected:\n"
            f"  docker compose -p {COMPOSE_PROJECT} -f {COMPOSE_FILE} logs postgres\n"
            f"  docker compose -p {COMPOSE_PROJECT} -f {COMPOSE_FILE} down -v   # to clean up",
            file=sys.stderr,
        )
        return 1

    if not args.keep:
        phase(12, "Tear down the drill stack")
        compose("down", "-v")
    else:
        print(f"\nStack left running on port {DRILL_PORT} (--keep).")
        print(f"  docker compose -p {COMPOSE_PROJECT} -f {COMPOSE_FILE} down -v   # when finished")

    return 0


def execute_drill() -> None:
    phase(0, "Start a clean drill cluster with WAL archiving on")
    compose("down", "-v")
    compose("up", "-d", "--build", "postgres")
    wait_for(postgres_accepting_connections, what="Postgres to accept connections")

    phase(1, "Apply CORA migrations (Atlas, out of band, as in production)")
    run(
        ["atlas", "migrate", "apply", "--env", "local"],
        cwd=ATLAS_DIR,
        extra_env={"DATABASE_URL": ATLAS_URL},
    )
    expected_revision = schema_revision()
    print(f"    schema revision: {expected_revision}")

    phase(2, "Create the pgBackRest stanza and verify archiving is wired")
    pgbackrest_live("stanza-create")
    # `check` forces a WAL segment through archive_command and confirms it
    # reached the repository. It is the one command that distinguishes a
    # configured archive from a working one, and it is why the drill can
    # fail here rather than three phases later with a confusing error.
    pgbackrest_live("check")
    # Postgres has been archiving since boot, into a stanza that did not
    # exist until the line above, so the archiver's lifetime counters
    # currently hold a burst of expected FileMissingError failures. Reset
    # them here so that from this point on a nonzero failure count means
    # something is actually wrong. This is a drill convenience, but the
    # underlying ordering is a real deployment concern: see the boot
    # ordering note in docs/stack/deployment.md.
    sql("SELECT pg_stat_reset_shared('archiver');")

    phase(3, "Seed Run A (will be inside the base backup)")
    seed_run(RUN_A, RUN_A_EVENTS)
    digest_a = stream_digest(RUN_A)
    print(f"    Run A fold digest: {digest_a}")

    phase(4, "Take a full backup")
    pgbackrest_live("--type=full", "backup")
    # pgBackRest picks the backup set to restore from by comparing its stop
    # time against the recovery target at WHOLE-SECOND resolution, and it
    # requires stop time STRICTLY LESS than the target. The drill writes
    # its streams in milliseconds, so without this pause the backup and the
    # target land in the same second and the restore fails with "unable to
    # find backup set with stop time less than ...". The pause is not a
    # test artefact: a real operator recovering to a moment inside the same
    # second the backup completed hits exactly this, and the fix there is
    # the same, name a target at least a second later.
    time.sleep(2)

    phase(5, "Seed Run B (AFTER the backup: only replayed WAL can restore it)")
    seed_run(RUN_B, RUN_B_EVENTS)
    digest_b = stream_digest(RUN_B)
    print(f"    Run B fold digest: {digest_b}")

    phase(6, "Mark the recovery target")
    target = sql("SELECT clock_timestamp();")
    print(f"    target time: {target}")
    # Recovery stops at the first transaction committing after the target,
    # so the target must fall strictly between Run B and Run C. A clock
    # gap here is what makes the Run C assertion meaningful rather than a
    # coin flip on timestamp resolution.
    time.sleep(2)

    phase(7, "Seed Run C (the damage: written after the target, must not return)")
    seed_run(RUN_C, RUN_C_EVENTS)
    digest_c_before = stream_digest(RUN_C)
    print(f"    Run C fold digest before restore: {digest_c_before}")
    # Name the WAL segment Run C landed in. Phase 8 asserts this segment
    # reached the repository, which is what makes the "Run C is absent"
    # check at the end mean something. Without it, an archive that simply
    # stopped early would produce the same passing result, and the drill
    # would be claiming point-in-time recovery on the strength of a gap.
    run_c_segment = sql("SELECT pg_walfile_name(pg_current_wal_lsn());")
    print(f"    Run C is in WAL segment: {run_c_segment}")

    phase(8, "Force the tail of WAL into the archive")
    # Postgres archives a segment when it fills or when archive_timeout
    # expires. Neither has happened for the segment holding Run B, so
    # without this switch the archive would end BEFORE the target and
    # recovery would stop short of Run B. In a real outage this gap is the
    # recovery point objective, bounded by archive_timeout (60s).
    sql("SELECT pg_switch_wal();")
    wait_for(
        lambda: archived_through(run_c_segment) and archiving_healthy(),
        what=f"the archiver to push {run_c_segment} and report healthy",
    )
    archived = sql("SELECT last_archived_wal FROM pg_stat_archiver;")
    failures = sql("SELECT failed_count FROM pg_stat_archiver;")
    print(f"    last archived WAL: {archived} (failures since stanza-create: {failures})")
    # Counters were reset once the stanza existed, so any failure here is a
    # real one rather than the expected bootstrap noise.
    if failures != "0":
        raise DrillError(f"WAL archiving reported {failures} failures after stanza-create")
    # WAL filenames are fixed-width hex, so a lexicographic comparison is
    # an ordering comparison. Run C's segment must have reached the
    # repository BEFORE the restore, otherwise its later absence proves
    # nothing about the recovery target.
    if archived < run_c_segment:
        raise DrillError(
            f"archive stops at {archived}, before Run C's segment "
            f"{run_c_segment}; the post-target check would be vacuous"
        )
    print("    Run C's segment reached the repository, so its later absence is the target's doing")
    # `verify` reads back every stored file checksum in the repository.
    # This is the moment it means the most: the WAL tail has been pushed
    # and the next phase destroys the source, so what verify certifies
    # here is the soundness of the only copy that is about to exist. A
    # deployment runs this on the weekly cora-backup-verify.timer; the
    # drill runs it once per exercise so the command's failure mode is a
    # rehearsed one.
    pgbackrest_live("verify")
    print("    repository verify: every stored checksum read back clean")

    phase(9, "DESTROY the cluster")
    compose("stop", "postgres")
    # Delete the contents of PGDATA, hidden entries included. This is a
    # real destruction, not a rename: nothing on this volume can be used
    # to reconstruct the database except the pgBackRest repository.
    compose(
        "run",
        "--rm",
        "--entrypoint",
        "bash",
        "pgbackrest",
        "-c",
        f"find {PGDATA} -mindepth 1 -delete",
    )
    # `test -d` first: on a MISSING directory `ls -A | wc -l` prints 0 and
    # exits 0, because the pipeline takes wc's status. Without the guard,
    # "PGDATA is empty" would also be the report for "PGDATA is gone".
    remaining = compose(
        "run",
        "--rm",
        "--entrypoint",
        "bash",
        "pgbackrest",
        "-c",
        f"test -d {PGDATA} && ls -A {PGDATA} | wc -l",
    ).splitlines()[-1]
    if remaining.strip() != "0":
        raise DrillError(f"PGDATA not empty after destruction: {remaining} entries")
    print("    PGDATA exists and is empty")

    phase(10, "Restore to the target time")
    # --delta is here so this is the SAME command the runbook gives. Without
    # it, pgBackRest refuses any target directory that contains files
    # ("ERROR: [040]: unable to restore to path ... because it contains
    # files"), which is every real restore, since corruption and bad
    # migrations leave PGDATA fully populated. The drill just emptied
    # PGDATA, so --delta self-disables here and the restore is a full one
    # either way; keeping the flag means the drill exercises the documented
    # command rather than a convenient variant of it.
    pgbackrest_offline(
        "--delta",
        "--type=time",
        f"--target={target}",
        "--target-action=promote",
        "restore",
    )
    compose("up", "-d", "postgres")
    wait_for(postgres_accepting_connections, what="Postgres to accept connections")
    wait_for(recovery_finished, what="recovery to complete and promote")

    phase(11, "Verify the event store at the domain level")
    checks: list[tuple[str, bool, str]] = []

    restored_revision = schema_revision()
    checks.append(
        (
            "schema revision matches",
            restored_revision == expected_revision,
            f"expected {expected_revision}, got {restored_revision}",
        )
    )

    for label, run_id, expected_events, expected_digest in (
        ("Run A (in base backup)", RUN_A, RUN_A_EVENTS, digest_a),
        ("Run B (WAL replay only)", RUN_B, RUN_B_EVENTS, digest_b),
    ):
        actual_events = stream_event_types(run_id)
        actual_digest = stream_digest(run_id)
        violations = commit_order_violations(run_id)
        checks.append(
            (
                f"{label}: event sequence",
                actual_events == expected_events,
                f"expected {expected_events}, got {actual_events}",
            )
        )
        checks.append(
            (
                f"{label}: fold digest",
                actual_digest == expected_digest,
                f"expected {expected_digest}, got {actual_digest}",
            )
        )
        checks.append(
            (
                f"{label}: commit order agrees with stream version",
                violations == 0,
                f"{violations} positions out of order",
            )
        )

    post_target = stream_event_types(RUN_C)
    checks.append(
        (
            f"Run C (after target, archived in {run_c_segment}): absent",
            post_target == [],
            f"expected no events, got {post_target}",
        )
    )

    print()
    failed = 0
    for name, ok, detail in checks:
        print(f"    {'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            print(f"          {detail}")
            failed += 1

    if failed:
        raise DrillError(f"{failed} of {len(checks)} domain checks failed")

    print(f"\n    {len(checks)} of {len(checks)} domain checks passed.")
    print(
        "    Run A survived the base backup, Run B was recovered from archived\n"
        "    WAL alone, and Run C was correctly left behind the recovery target."
    )


if __name__ == "__main__":
    sys.exit(main())
