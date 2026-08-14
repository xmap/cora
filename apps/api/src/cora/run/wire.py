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

## BC-internal ObservationStore wiring

`append_observations` needs a `ObservationStore` adapter. Per the
per-category-writer pattern (mirrors Decision BC's InferenceStore
and Conduit's VerdictStore), the store is built LOCALLY here from
`deps.pool` (Postgres in production) or as `InMemoryObservationStore`
in `app_env=test`. NOT promoted to Kernel fields.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.idempotency import (
    NOOP_DESERIALIZE,
    NOOP_SERIALIZE,
    with_idempotency,
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.run.aggregates.run import (
    InMemoryObservationStore,
    ObservationStore,
    PostgresObservationStore,
)
from cora.run.features import (
    abort_run,
    adjust_run,
    append_observations,
    complete_run,
    get_run,
    hold_run,
    list_runs,
    record_witnessed_run,
    resume_run,
    start_run,
    stop_run,
    truncate_run,
)

_BC = "run"


@dataclass(frozen=True)
class RunHandlers:
    """The Run BC's handler bundle, each closed over Kernel."""

    start_run: start_run.IdempotentHandler
    record_witnessed_run: record_witnessed_run.Handler
    complete_run: complete_run.Handler
    abort_run: abort_run.Handler
    hold_run: hold_run.Handler
    resume_run: resume_run.Handler
    stop_run: stop_run.Handler
    truncate_run: truncate_run.Handler
    adjust_run: adjust_run.IdempotentHandler
    append_observations: append_observations.Handler
    get_run: get_run.Handler
    list_runs: list_runs.Handler


def wire_run(deps: Kernel) -> RunHandlers:
    """Build the Run BC handlers from shared dependencies."""
    observation_store: ObservationStore = (
        PostgresObservationStore(deps.pool) if deps.pool is not None else InMemoryObservationStore()
    )
    return RunHandlers(
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
            get_run.bind(deps),
            command_name="GetRun",
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
