"""Compose the Trust BC's handlers from `Kernel`.

`wire_trust(deps)` is invoked once from the FastAPI lifespan and the
returned `TrustHandlers` bundle is stored on `app.state.trust`. Routes
and MCP tools pull their handler out of that bundle. New slices
(commands or queries) add a new field on `TrustHandlers` and a single
line in this factory.

Cross-cutting decorators applied here mirror Access (composition order
matters -- innermost first):

1. `bind(deps)` -- bare handler.
2. `with_idempotency` (create-style commands only) -- Idempotency-Key
   support (`cora.infrastructure.idempotency`). Wrapped before tracing
   so cache-hits and cache-misses both attribute to the tracing span.
3. `with_tracing` -- OTel span around every handler call. Records
   `cora.bc`, `cora.command` / `cora.query` attributes.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.trust.features import (
    abort_visit,
    cancel_visit,
    check_in_visit,
    check_out_visit,
    complete_visit,
    define_conduit,
    define_policy,
    define_surface,
    define_zone,
    evaluate_policy,
    get_surface,
    hold_visit,
    list_conduits,
    list_permissions,
    list_policies,
    list_zones,
    record_visit_arrival,
    register_visit,
    release_control_of_surface,
    resume_visit,
    start_visit,
    take_control_of_surface,
    void_visit,
)

_BC = "trust"


@dataclass(frozen=True)
class TrustHandlers:
    """The Trust BC's handler bundle, each closed over Kernel.

    Five aggregates: `Zone`, `Conduit`, `Surface`, `Policy`, `Visit`.
    Genesis commands (`define_*`, `register_visit`) are idempotency-
    wrapped; lifecycle transitions on Visit (`arrive`/`start`/`hold`/
    `resume`/`complete`/`cancel`/`abort`/`void`) use the bare Handler
    Protocol -- they are operator gestures that mutate one stream
    without create-style idempotency semantics. Query slices
    (`evaluate_policy`, `get_surface`, `list_*`) are bare since queries
    don't mutate.
    """

    define_zone: define_zone.IdempotentHandler
    define_conduit: define_conduit.IdempotentHandler
    define_policy: define_policy.IdempotentHandler
    define_surface: define_surface.IdempotentHandler
    register_visit: register_visit.IdempotentHandler
    record_visit_arrival: record_visit_arrival.Handler
    start_visit: start_visit.Handler
    hold_visit: hold_visit.Handler
    resume_visit: resume_visit.Handler
    complete_visit: complete_visit.Handler
    cancel_visit: cancel_visit.Handler
    abort_visit: abort_visit.Handler
    void_visit: void_visit.Handler
    check_in_visit: check_in_visit.Handler
    check_out_visit: check_out_visit.Handler
    take_control_of_surface: take_control_of_surface.Handler
    release_control_of_surface: release_control_of_surface.Handler
    evaluate_policy: evaluate_policy.Handler
    get_surface: get_surface.Handler
    list_zones: list_zones.Handler
    list_conduits: list_conduits.Handler
    list_policies: list_policies.Handler
    list_permissions: list_permissions.Handler


def wire_trust(deps: Kernel) -> TrustHandlers:
    """Build the Trust BC handlers from shared dependencies."""
    return TrustHandlers(
        define_zone=with_tracing(
            with_idempotency(
                define_zone.bind(deps),
                deps.idempotency_store,
                command_name="DefineZone",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineZone",
            bc=_BC,
        ),
        define_conduit=with_tracing(
            with_idempotency(
                define_conduit.bind(deps),
                deps.idempotency_store,
                command_name="DefineConduit",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineConduit",
            bc=_BC,
        ),
        define_policy=with_tracing(
            with_idempotency(
                define_policy.bind(deps),
                deps.idempotency_store,
                command_name="DefinePolicy",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefinePolicy",
            bc=_BC,
        ),
        define_surface=with_tracing(
            with_idempotency(
                define_surface.bind(deps),
                deps.idempotency_store,
                command_name="DefineSurface",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineSurface",
            bc=_BC,
        ),
        register_visit=with_tracing(
            with_idempotency(
                register_visit.bind(deps),
                deps.idempotency_store,
                command_name="RegisterVisit",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterVisit",
            bc=_BC,
        ),
        record_visit_arrival=with_tracing(
            record_visit_arrival.bind(deps),
            command_name="RecordVisitArrival",
            bc=_BC,
        ),
        start_visit=with_tracing(
            start_visit.bind(deps),
            command_name="StartVisit",
            bc=_BC,
        ),
        hold_visit=with_tracing(
            hold_visit.bind(deps),
            command_name="HoldVisit",
            bc=_BC,
        ),
        resume_visit=with_tracing(
            resume_visit.bind(deps),
            command_name="ResumeVisit",
            bc=_BC,
        ),
        complete_visit=with_tracing(
            complete_visit.bind(deps),
            command_name="CompleteVisit",
            bc=_BC,
        ),
        cancel_visit=with_tracing(
            cancel_visit.bind(deps),
            command_name="CancelVisit",
            bc=_BC,
        ),
        abort_visit=with_tracing(
            abort_visit.bind(deps),
            command_name="AbortVisit",
            bc=_BC,
        ),
        void_visit=with_tracing(
            void_visit.bind(deps),
            command_name="VoidVisit",
            bc=_BC,
        ),
        check_in_visit=with_tracing(
            check_in_visit.bind(deps),
            command_name="CheckInVisit",
            bc=_BC,
        ),
        check_out_visit=with_tracing(
            check_out_visit.bind(deps),
            command_name="CheckOutVisit",
            bc=_BC,
        ),
        take_control_of_surface=with_tracing(
            take_control_of_surface.bind(deps),
            command_name="TakeControlOfSurface",
            bc=_BC,
        ),
        release_control_of_surface=with_tracing(
            release_control_of_surface.bind(deps),
            command_name="ReleaseControlOfSurface",
            bc=_BC,
        ),
        evaluate_policy=with_tracing(
            evaluate_policy.bind(deps),
            command_name="EvaluatePolicy",
            bc=_BC,
            kind="query",
        ),
        get_surface=with_tracing(
            get_surface.bind(deps),
            command_name="GetSurface",
            bc=_BC,
            kind="query",
        ),
        list_zones=with_tracing(
            list_zones.bind(deps),
            command_name="ListZones",
            bc=_BC,
            kind="query",
        ),
        list_conduits=with_tracing(
            list_conduits.bind(deps),
            command_name="ListConduits",
            bc=_BC,
            kind="query",
        ),
        list_policies=with_tracing(
            list_policies.bind(deps),
            command_name="ListPolicies",
            bc=_BC,
            kind="query",
        ),
        list_permissions=with_tracing(
            list_permissions.bind(deps),
            command_name="ListPermissions",
            bc=_BC,
            kind="query",
        ),
    )
