"""Compose the Calibration BC's handlers from `Kernel`.

`wire_calibration(deps)` is invoked once from the FastAPI lifespan
and the returned `CalibrationHandlers` bundle is stored on
`app.state.calibration`. Routes and MCP tools pull their handler out
of that bundle. New slices add a new field on `CalibrationHandlers`
and a single line in this factory.

Cross-cutting decorators applied here:

  1. `bind(deps)` — bare handler.
  2. `with_idempotency` (create-style commands only) — Idempotency-Key
     support. Wrapped before tracing so cache-hits and cache-misses
     both attribute to the tracing span.
  3. `with_tracing` — OTel span around every handler call.

## Wired handlers (12a-2)

  - `define_calibration` (create-style; idempotency-wrapped)
  - `append_calibration_revision`
                          (update-style; idempotency-wrapped per design
                          memo — agent subscribers are the primary
                          callers and need exactly-once-effective
                          semantics across retries)
  - `get_calibration`    (query)
  - `list_calibrations`  (query)
"""

from dataclasses import dataclass
from uuid import UUID

from cora.calibration.features import (
    append_calibration_revision,
    define_calibration,
    get_calibration,
    list_calibrations,
    publish_revision,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "calibration"


@dataclass(frozen=True)
class CalibrationHandlers:
    """The Calibration BC's handler bundle, each closed over Kernel."""

    define_calibration: define_calibration.IdempotentHandler
    append_calibration_revision: append_calibration_revision.IdempotentHandler
    publish_revision: publish_revision.IdempotentHandler
    get_calibration: get_calibration.Handler
    list_calibrations: list_calibrations.Handler


def wire_calibration(deps: Kernel) -> CalibrationHandlers:
    """Build the Calibration BC handlers from shared dependencies."""
    return CalibrationHandlers(
        define_calibration=with_tracing(
            with_idempotency(
                define_calibration.bind(deps),
                deps.idempotency_store,
                command_name="DefineCalibration",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineCalibration",
            bc=_BC,
        ),
        append_calibration_revision=with_tracing(
            with_idempotency(
                append_calibration_revision.bind(deps),
                deps.idempotency_store,
                command_name="AppendCalibrationRevision",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="AppendCalibrationRevision",
            bc=_BC,
        ),
        publish_revision=with_tracing(
            with_idempotency(
                publish_revision.bind(deps),
                deps.idempotency_store,
                command_name="PublishCalibrationRevision",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="PublishCalibrationRevision",
            bc=_BC,
        ),
        get_calibration=with_tracing(
            get_calibration.bind(deps),
            command_name="GetCalibration",
            bc=_BC,
            kind="query",
        ),
        list_calibrations=with_tracing(
            list_calibrations.bind(deps),
            command_name="ListCalibrations",
            bc=_BC,
            kind="query",
        ),
    )
