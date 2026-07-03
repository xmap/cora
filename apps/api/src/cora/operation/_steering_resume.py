"""Reconstruct a steered loop's observation history from the recorded outcomes.

The crux of RESUME: rebuild the `tuple[SteeringObservation, ...]` the brain saw
across the already-closed passes of an interrupted steered conduct, from the
recorded `Outcome` rows alone, so a resumed loop re-conditions the brain from
the record instead of re-measuring hardware (strategy A per the resume-semantics
research: recorded results are replayed, side effects are not re-run).

## Self-describing rows: no join, no off-by-one

Each `Outcome` row carries BOTH the coordinate it measured at (`point`, the x)
and the measured values there (`measurements`, the y). So reconstruction is a
plain sort-by-`iteration_index` then map: row -> observation. There is no join
to `ProcedureIterationEnded.advised_next_point` and no pass-k-to-pass-(k-1)
pairing, which removes the off-by-one and, critically, survives an abandoned
pass: a mid-crash pass leaves an index gap (no outcome row was written for it,
or a stale one under a now-unused index), and a sort tolerates gaps where a
positional pairing could not.

The brain does not depend on the index being dense: every shipped decider reads
its cursor from `len(evidence.observations)` (the count of prior measurements),
not from any iteration number, so a gapped `iteration_index` never mis-cues the
brain. The index is retained only as the stable sort key + an audit
cross-reference to the FSM iteration that produced the row.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from cora.operation.ports.control_port import ActuationKind
from cora.operation.ports.decide_port import SteeringObservation
from cora.operation.ports.measurement import Measurement, MeasurementKind, Quality
from cora.shared.steering import SteeringPoint

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cora.operation.ports.procedure_outcome_lookup import RecordedOutcome


def reconstruct_observations(
    outcomes: Sequence[RecordedOutcome],
) -> tuple[SteeringObservation, ...]:
    """Rebuild the observation history the brain saw, from recorded outcomes.

    `outcomes` are the recorded `RecordedOutcome` rows for the procedure, in any
    order; this sorts them ascending by `iteration_index` (the recorded pass
    order) and maps each self-describing row to a `SteeringObservation`. Index
    gaps (from an abandoned mid-crash pass) are tolerated: the sort preserves
    pass order regardless, and the brain reads its cursor from the observation
    count, not the index. Returns observations in pass order, ready to seed a
    resumed loop's evidence and to re-condition the brain at the frontier.
    """
    ordered = sorted(outcomes, key=lambda row: row.iteration_index)
    return tuple(
        SteeringObservation(
            point=SteeringPoint(coordinates=dict(row.point)),
            measurements=tuple(_measurement_from_dict(m) for m in row.measurements),
            artifact_ref=None,
            actuation_kind=(
                ActuationKind(row.actuation_kind) if row.actuation_kind is not None else None
            ),
            succeeded=row.succeeded,
        )
        for row in ordered
    )


def _measurement_from_dict(raw: dict[str, Any]) -> Measurement:
    """Rebuild a `Measurement` from an Outcome row's recorded measurement dict.

    Symmetric with `conductor._outcome_measurement_to_dict`: reads back name,
    value, kind, quality, quality_detail, units, and the ISO-8601 produced_at.
    Defensive on the optional fields so a leaner recorded shape still rebuilds.
    """
    produced_at_raw = raw.get("produced_at")
    produced_at = (
        datetime.fromisoformat(produced_at_raw) if isinstance(produced_at_raw, str) else _EPOCH
    )
    kind: MeasurementKind = raw.get("kind", "Scalar")
    quality: Quality = raw.get("quality", "Good")
    return Measurement(
        value=raw.get("value"),
        kind=kind,
        quality=quality,
        produced_at=produced_at,
        quality_detail=raw.get("quality_detail", ""),
        name=raw.get("name", ""),
        units=raw.get("units"),
    )


_EPOCH = datetime.fromtimestamp(0, tz=UTC)


__all__ = [
    "reconstruct_observations",
]
