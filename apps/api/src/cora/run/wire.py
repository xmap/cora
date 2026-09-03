"""Compose the Run BC's handlers from `Kernel`.

`wire_run(deps)` is invoked once from the FastAPI lifespan and the
returned `RunHandlers` bundle is stored on `app.state.run`. Routes
and MCP tools pull their handler out of that bundle.

Cross-cutting decorators applied here mirror Recipe / Equipment /
Trust / Subject / Access (composition order matters — innermost
first):

1. `bind(deps)` — bare handler.
2. `with_idempotency` (create-style commands only) — Idempotency-Key
   support. Transition handlers (complete / abort / hold / resume /
   stop) do NOT idempotency-wrap: they're update-style, the strict-
   not-idempotent guard already rejects double-application, and the
   ConcurrencyError on stale expected_version handles the
   double-submit case at the persistence layer.
3. `with_tracing` — OTel span around every handler call.

`start_run` is the create-style genesis (idempotency-wrapped). The
FSM closes via four terminal transitions (`complete` / `abort` /
`stop` / `truncate`) and a bidirectional pause cycle
(`hold` / `resume`) — all update-style with bare Handler protocols,
strict-not-idempotent (the guard rejects double-application and
ConcurrencyError catches the persistence-layer double-submit case).

`record_witnessed_run` is a second, independent genesis (the witnessed
path). NOT idempotency-wrapped despite being create-style: the Run id
is fresh and random per call, so there is no Idempotency-Key to
collapse a retry against. In-process-only; no route, no MCP tool ever
call it.

`record_witnessed_run_outcome` closes the witnessed path: update-style,
bare Handler protocol, same posture as the four driven terminals (strict-
not-idempotent, ConcurrencyError handles the double-submit case). Also
in-process-only; no route, no MCP tool ever call it.

`append_observations` writes the polymorphic sensor / motor observation
logbook (SOSA `sampling_procedure` discriminator; lazy open-on-first-
write). Not idempotency-wrapped: natural idempotence via the
at-most-one-open-logbook invariant + entry-store PK.

`adjust_run` is mid-flight parameter steering for in-progress Runs.
Idempotency-wrapped per the create-style retry-safe convention
(operator retries on flaky network must NOT double-apply patches;
same logic as `amend_clearance` and `add_run_to_campaign`). The
handler is longhand (not the update-handler factory) because it
cross-loads Plan → Practice → Method to surface the Method's
`parameters_schema` for merged-result validation.

## BC-internal ObservationStore + FeedHeartbeatStore + CapturePathStore wiring

`append_observations` needs a `ObservationStore` adapter. Per the
per-category-writer pattern (mirrors Decision BC's InferenceStore
and Conduit's VerdictStore), the store is built LOCALLY here from
`deps.pool` (Postgres in production) or as `InMemoryObservationStore`
in `app_env=test`. NOT promoted to Kernel fields.

`feed_heartbeat_store` is surfaced on the bundle the same way
`EnclosureHandlers.permit_probe_store` is: not a command handler, so
routes/tools never touch it, but the composition-root lifespan
(`_capture_progress_feeder.py`'s feeder, slice 10) needs the write
store directly, not wrapped behind a command.

`capture_path_store` (slice 13) follows the identical construction
shape (built locally from `deps.pool`), but NOT the identical wiring:
it is surfaced on the bundle for the composition root's
`RunTranslator` to write through (it verifies the observed path
against the Run's own BEGUN time before writing, so the write cannot be
a plain command) AND passed into `get_run.bind(deps, capture_path_store=...)`,
which resolves it inside the handler exactly the way `get_actor.bind(deps,
profile_store=...)` resolves `ProfileStore` -- see `get_run/handler.py`'s
`RunView`. It is deliberately NEVER passed into `list_runs.bind()`.
`list_runs` is one shared handler instance read by every internal
composition-root caller (`rebuild_open_captures`, the supervisor and
initiator watchdogs) as well as the REST/MCP route; resolving personal
data there would expose it to callers that only need `run_id` off each
page item, and would do so under one bulk, cursor-paginated grant no
different in kind from the coarse `ListRuns` authorization this BC's
own `list_query.py` already documents as unscoped-per-row (BOLA
deferred until ReBAC). `get_run` avoids the FIRST problem outright (no
internal caller exists today) regardless of how its own authorization
eventually gets scoped, mirroring why `list_actors` never touches
`ProfileStore` while `get_actor` does. Kernel-level placement is still
wrong for the same reason as before: this is a PII vault, so
`ProfileStore` would be the closer precedent by subject matter, but
`ProfileStore` is Kernel-level specifically because it is genuinely
cross-BC-shared (Access + Agent); this store has exactly one
BC.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from cora.infrastructure.idempotency import (
    NOOP_DESERIALIZE,
    NOOP_SERIALIZE,
    with_idempotency,
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.run.adapters import InMemoryRunObservationTrail, PostgresRunObservationTrail
from cora.run.aggregates.run import (
    CapturePathStore,
    CaptureProbeStore,
    ExperimentIdentityStore,
    FeedHeartbeatStore,
    InMemoryCapturePathStore,
    InMemoryCaptureProbeStore,
    InMemoryExperimentIdentityStore,
    InMemoryFeedHeartbeatStore,
    InMemoryObservationStore,
    ObservationStore,
    PostgresCapturePathStore,
    PostgresCaptureProbeStore,
    PostgresExperimentIdentityStore,
    PostgresFeedHeartbeatStore,
    PostgresObservationStore,
)
from cora.run.features import (
    abort_run,
    adjust_run,
    append_observations,
    complete_run,
    get_run,
    get_run_history,
    hold_run,
    list_runs,
    record_witnessed_run,
    record_witnessed_run_outcome,
    resume_run,
    start_run,
    stop_run,
    truncate_run,
)

if TYPE_CHECKING:
    from cora.run.ports.run_observation_trail import RunObservationTrail

_BC = "run"


@dataclass(frozen=True)
class RunHandlers:
    """The Run BC's handler bundle, each closed over Kernel."""

    start_run: start_run.IdempotentHandler
    record_witnessed_run: record_witnessed_run.Handler
    record_witnessed_run_outcome: record_witnessed_run_outcome.Handler
    complete_run: complete_run.Handler
    abort_run: abort_run.Handler
    hold_run: hold_run.Handler
    resume_run: resume_run.Handler
    stop_run: stop_run.Handler
    truncate_run: truncate_run.Handler
    adjust_run: adjust_run.IdempotentHandler
    append_observations: append_observations.Handler
    get_run: get_run.Handler
    get_run_history: get_run_history.Handler
    list_runs: list_runs.Handler
    feed_heartbeat_store: FeedHeartbeatStore
    """The feed-heartbeat trail's write store. Surfaced on the bundle,
    not a handler, mirroring `EnclosureHandlers.permit_probe_store`
    exactly: a composition-root lifespan needs this dependency
    directly, and it isn't itself a command handler."""
    capture_path_store: CapturePathStore
    """Slice 13's PII vault store for a witnessed Run's observed
    capture file path. Surfaced on the bundle for the same reason as
    `feed_heartbeat_store`: `RunTranslator` (composition root)
    writes through it directly after its own dual-clock guard passes.
    `get_run.bind()` (single-entity, mirroring `get_actor`) reads
    through the SAME instance; `list_runs` deliberately never touches
    it at all -- see this class's own module docstring."""
    experiment_identity_store: ExperimentIdentityStore
    """Slice 14a's vault store for a witnessed Run's proposal / ESAF /
    ESAF-DOI experiment identity. Same surfacing reason and the same
    `list_runs`-never-touches-it posture as `capture_path_store`:
    `RunTranslator`'s `CaptureExperimentIdentityReader` writes through it
    directly, and `get_run.bind()` reads through the SAME instance."""
    capture_probe_store: CaptureProbeStore
    """Slice 16's write store for the capture-watch coverage trail.
    Surfaced on the bundle for the same reason as `feed_heartbeat_store`:
    `RunTranslator` (composition root) writes through it directly.
    UNLIKE `capture_path_store` / `experiment_identity_store`, never
    passed to `get_run.bind()` or any other handler: this store is not
    scoped by `run_id` at all (see `entries_run_capture_probes`'
    migration header), so there is no single-Run read to resolve it
    against."""


def wire_run(deps: Kernel) -> RunHandlers:
    """Build the Run BC handlers from shared dependencies."""
    observation_store: ObservationStore
    run_observation_trail: RunObservationTrail
    if deps.pool is not None:
        observation_store = PostgresObservationStore(deps.pool)
        run_observation_trail = PostgresRunObservationTrail(deps.pool)
    else:
        in_memory_observations = InMemoryObservationStore()
        observation_store = in_memory_observations
        run_observation_trail = InMemoryRunObservationTrail(in_memory_observations)
    feed_heartbeat_store: FeedHeartbeatStore = (
        PostgresFeedHeartbeatStore(deps.pool)
        if deps.pool is not None
        else InMemoryFeedHeartbeatStore()
    )
    capture_path_store: CapturePathStore = (
        PostgresCapturePathStore(deps.pool) if deps.pool is not None else InMemoryCapturePathStore()
    )
    experiment_identity_store: ExperimentIdentityStore = (
        PostgresExperimentIdentityStore(deps.pool)
        if deps.pool is not None
        else InMemoryExperimentIdentityStore()
    )
    capture_probe_store: CaptureProbeStore = (
        PostgresCaptureProbeStore(deps.pool)
        if deps.pool is not None
        else InMemoryCaptureProbeStore()
    )
    return RunHandlers(
        feed_heartbeat_store=feed_heartbeat_store,
        capture_path_store=capture_path_store,
        experiment_identity_store=experiment_identity_store,
        capture_probe_store=capture_probe_store,
        start_run=with_tracing(
            with_idempotency(
                start_run.bind(deps),
                deps.idempotency_store,
                command_name="StartRun",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="StartRun",
            bc=_BC,
        ),
        record_witnessed_run=with_tracing(
            record_witnessed_run.bind(deps),
            command_name="RecordWitnessedRun",
            bc=_BC,
        ),
        record_witnessed_run_outcome=with_tracing(
            record_witnessed_run_outcome.bind(deps),
            command_name="RecordWitnessedRunOutcome",
            bc=_BC,
        ),
        complete_run=with_tracing(
            complete_run.bind(deps),
            command_name="CompleteRun",
            bc=_BC,
        ),
        abort_run=with_tracing(
            abort_run.bind(deps),
            command_name="AbortRun",
            bc=_BC,
        ),
        hold_run=with_tracing(
            hold_run.bind(deps),
            command_name="HoldRun",
            bc=_BC,
        ),
        resume_run=with_tracing(
            resume_run.bind(deps),
            command_name="ResumeRun",
            bc=_BC,
        ),
        stop_run=with_tracing(
            stop_run.bind(deps),
            command_name="StopRun",
            bc=_BC,
        ),
        truncate_run=with_tracing(
            truncate_run.bind(deps),
            command_name="TruncateRun",
            bc=_BC,
        ),
        adjust_run=with_tracing(
            with_idempotency(
                adjust_run.bind(deps),
                deps.idempotency_store,
                command_name="AdjustRun",
                # Handler returns None (204-on-success). No payload to
                # cache; the cache hit replays "success with None"
                # via the shared no-op codecs hoisted to
                # cora.infrastructure.idempotency.
                serialize_result=NOOP_SERIALIZE,
                deserialize_result=NOOP_DESERIALIZE,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="AdjustRun",
            bc=_BC,
        ),
        append_observations=with_tracing(
            append_observations.bind(deps, observation_store=observation_store),
            command_name="AppendObservations",
            bc=_BC,
        ),
        get_run=with_tracing(
            get_run.bind(
                deps,
                capture_path_store=capture_path_store,
                experiment_identity_store=experiment_identity_store,
            ),
            command_name="GetRun",
            bc=_BC,
            kind="query",
        ),
        get_run_history=with_tracing(
            get_run_history.bind(deps, observation_trail=run_observation_trail),
            command_name="GetRunHistory",
            bc=_BC,
            kind="query",
        ),
        list_runs=with_tracing(
            list_runs.bind(deps),
            command_name="ListRuns",
            bc=_BC,
            kind="query",
        ),
    )
