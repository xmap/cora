"""The `CompleteRun` command — intent dataclass for this slice.

Single-source happy-path terminal: `Running -> Completed`. The bare
operator-facing form is just `run_id`; no body at the API layer. The
optional conduct-provenance fields are server-supplied by the compute
CONDUCT runtime (`Reckoner`), never operator input, mirroring
`CompleteProcedure.actuation_kind`.

Per-event timestamping (`occurred_at`) and the new event id are
injected by the handler from infrastructure ports — same capture-
don't-recompute principle as every other slice.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CompleteRun:
    """Mark an existing Run as completed (happy-path terminal).

    `actuation_kind` is the raw `ActuationKind` value (Physical /
    Simulated / Hybrid) the compute runtime observed for a conducted
    Run, or None for a complete issued outside a conduct. The decider
    snapshots it onto `RunCompleted` so the Data BC reads it back to
    gate Dataset promotion. `producing_job_id` (the compute substrate's
    job handle) and `artifact_uri` (where the job wrote its output)
    ride the event as audit / handoff breadcrumbs; both None outside a
    conduct.
    """

    run_id: UUID
    actuation_kind: str | None = None
    producing_job_id: str | None = None
    artifact_uri: str | None = None
