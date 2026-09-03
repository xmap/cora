"""RunSummaryProjection: folds the Run aggregate's lifecycle events
into the `proj_run_summary` read model that backs `GET /runs`.

Subscribed events (genesis + 6 lifecycle transitions + 2 cross-
aggregate membership transitions + 1 attribution-stamping
transition):
  - RunStarted             -> INSERT (status=Running, name + plan_id +
                                      subject_id? + raid? + running_since +
                                      override_parameters_present +
                                      campaign_id? +
                                      pinned_calibration_ids +
                                      conduct_mode + capture_code? from
                                      payload)
  - RunHeld                -> UPDATE status=Held
  - RunResumed             -> UPDATE status=Running + running_since reset
  - RunCompleted           -> UPDATE status=Completed   (terminal)
  - RunAborted             -> UPDATE status=Aborted     (terminal)
  - RunStopped             -> UPDATE status=Stopped     (terminal)
  - RunTruncated           -> UPDATE status=Truncated   (terminal)
  - RunAddedToCampaign     -> UPDATE campaign_id = $2
                              (post-hoc add via add_run_to_campaign)
  - RunRemovedFromCampaign -> UPDATE campaign_id = NULL
                              (remove via remove_run_from_campaign)
  - RunAdjusted            -> UPDATE last_adjusted_by = $2 AND recompute
                              snr_limit + expected_observation_interval_seconds
                              from the re-snapshotted effective_parameters
                              (overwrite-on-each-adjust; mirrors the
                              aggregate-state attribution-half per
                              [[project_fold_symmetry_design]])

All branches idempotent. Genesis-event payload values (plan_id,
subject_id, raid, override_parameters_present, pinned_calibration_ids,
conduct_mode) land on INSERT and never change (AsShot invariant for
pinned_calibration_ids; conduct_mode is immutable for the same reason:
who drove the act cannot change after genesis); lifecycle UPDATEs
only touch `status`; membership UPDATEs only touch `campaign_id`.

`override_parameters_present` is TRUE iff RunStarted's
`override_parameters` payload was non-empty (operator customized
parameters at start time vs. just used Plan defaults). The full
overrides + effective_parameters dicts live on the event itself,
loaded on demand via `get_run` fold-on-read; the boolean is the
list-endpoint filter primitive. See
[[project_run_parameters_design]] §6g-c for the locked design and
the future JSONB-column trigger (promote when key-level value
filtering becomes a pilot need).

`campaign_id` (Campaign Watch #10) serves the "list Runs in
Campaign X" query path without folding individual Run streams or
2-hop-joining through `proj_campaign_summary.run_ids`.
Forward-compat: legacy RunStarted payloads lack the key entirely;
`.get("campaign_id")` returns None and the column stays NULL. See
[[project_campaign_design]] §"bidirectional composition".

`pinned_calibration_ids` surfaces the AsShot pin set so
downstream consumers (Dataset back-fill, future RunDebriefer /
RotationCenterRefiner subscribers) can read "which calibrations
was this Run acquired against?" without folding the Run stream.
Forward-compat: legacy RunStarted payloads lack the key entirely;
`.get("pinned_calibration_ids", [])` returns `[]` so legacy rows land
with an empty UUID array.

`capture_code` (slice 13) surfaces the `Identifier(scheme="capture-code")`
a witnessed genesis already stamps onto `RunStarted.external_refs`, so
`list_runs` can filter/resolve without folding the Run stream. NULL for
a Conducted Run (no external_refs entry at all) and, defensively, for
any Witnessed row whose genesis somehow lacked one: this module's own
`_extract_capture_code` returns `None` in both cases, mirroring the
same "absent, not erroring" posture the public sibling function of the
same name (`cora.run.aggregates.run.state.extract_capture_code`)
already takes against the folded aggregate state. Deliberately NOT the
resolved capture PATH: that value is
personal data and lives only in the `run_capture_path` PII vault,
resolved at query time, never folded into this projection.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import math
from datetime import datetime
from typing import Any
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_RUN_SQL = """
INSERT INTO proj_run_summary
    (run_id, name, plan_id, subject_id, raid, status, created_at, running_since,
     override_parameters_present, campaign_id, pinned_calibration_ids,
     snr_limit, expected_observation_interval_seconds, conduct_mode, capture_code)
VALUES ($1, $2, $3, $4, $5, 'Running', $6, $6, $7, $8, $9::uuid[], $10, $11, $12, $13)
ON CONFLICT (run_id) DO NOTHING
"""

_CAPTURE_CODE_SCHEME = "capture-code"


def _extract_capture_code(external_refs: list[dict[str, Any]]) -> str | None:
    """Find the `Identifier(scheme="capture-code")` entry's value in a
    raw `RunStarted.external_refs` payload list.

    Mirrors the public sibling `extract_capture_code` in
    `cora.run.aggregates.run.state` (which does the same lookup against
    the folded aggregate state's `frozenset[Identifier]`, and is what
    `_run_translator.py` and `get_run`'s handler both call); this one
    operates on the raw JSON list a stored event payload carries, a
    genuinely different input type, so it stays a separate function.
    `None` for a Conducted Run (empty list) and, defensively, for a
    Witnessed row that somehow lacks the ref: never an error.
    """
    for ref in external_refs:
        if ref.get("scheme") == _CAPTURE_CODE_SCHEME:
            value = ref.get("value")
            return str(value) if value is not None else None
    return None


_UPDATE_STATUS_SQL = """
UPDATE proj_run_summary
SET status = $2, updated_at = now()
WHERE run_id = $1
"""

# RunResumed flips Held -> Running AND resets running_since to the resume
# timestamp, so the Run-liveness signal measures only the current Running
# interval (not the time spent Held). Status is the literal 'Running' since
# RunResumed always lands there.
_UPDATE_RESUMED_SQL = """
UPDATE proj_run_summary
SET status = 'Running', running_since = $2, updated_at = now()
WHERE run_id = $1
"""

_UPDATE_CAMPAIGN_SQL = """
UPDATE proj_run_summary
SET campaign_id = $2, updated_at = now()
WHERE run_id = $1
"""

# RunAdjusted re-snapshots effective_parameters, so it MUST recompute the
# closed-loop rule inputs in lockstep: a mid-run re-cadence (changing the
# snr limit or the expected interval) would otherwise leave Rule R / Rule Q
# evaluating against stale start-time inputs, the exact stale-baseline
# failure the watchdog exists to prevent. Recompute lives in the SAME arm
# (RunAdjusted is already subscribed; no new subscription).
_UPDATE_ADJUSTED_SQL = """
UPDATE proj_run_summary
SET last_adjusted_by = $2,
    snr_limit = $3,
    expected_observation_interval_seconds = $4,
    updated_at = now()
WHERE run_id = $1
"""

_EVENT_TO_STATUS = {
    "RunHeld": "Held",
    "RunCompleted": "Completed",
    "RunAborted": "Aborted",
    "RunStopped": "Stopped",
    "RunTruncated": "Truncated",
}


def _positive_finite_or_none(raw: object) -> float | None:
    """Coerce a raw effective-parameter value to a positive finite float,
    else None. NULL/non-numeric/NaN/Infinity/<=0 all map to None, which
    disables the corresponding rule for the Run (cannot-tell -> defer)."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0.0 else None


def _rule_inputs(payload: dict[str, Any]) -> tuple[float | None, float | None]:
    """Derive (snr_limit, expected_observation_interval_seconds) from a
    RunStarted / RunAdjusted payload's effective_parameters by reading the
    operator-declared conventional keys. Absent or degenerate -> None.
    Forward-compat: legacy payloads lack effective_parameters entirely."""
    effective = payload.get("effective_parameters") or {}
    snr_limit = _positive_finite_or_none(effective.get("snr_limit"))
    expected_interval = _positive_finite_or_none(
        effective.get("expected_observation_interval_seconds")
    )
    return snr_limit, expected_interval


class RunSummaryProjection:
    """Maintains the `proj_run_summary` read model."""

    name = "proj_run_summary"
    subscribed_event_types = frozenset(
        {
            "RunStarted",
            "RunHeld",
            "RunResumed",
            "RunCompleted",
            "RunAborted",
            "RunStopped",
            "RunTruncated",
            "RunAddedToCampaign",
            "RunRemovedFromCampaign",
            "RunAdjusted",
        }
    )

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        if event.event_type == "RunStarted":
            payload = event.payload
            subject_id = UUID(payload["subject_id"]) if payload.get("subject_id") else None
            # Forward-compat: legacy RunStarted payloads have no
            # override_parameters key; bool({}) is FALSE so legacy
            # rows backfill cleanly.
            overrides_present = bool(payload.get("override_parameters"))
            # Forward-compat: legacy RunStarted payloads have no
            # campaign_id key; .get() returns None so legacy rows
            # land with campaign_id IS NULL.
            campaign_id_raw = payload.get("campaign_id")
            campaign_id = UUID(campaign_id_raw) if campaign_id_raw else None
            # Forward-compat: legacy RunStarted payloads have no
            # pinned_calibration_ids key; .get(..., []) returns [] so legacy
            # rows land with an empty UUID array.
            pinned_calibration_ids = [UUID(p) for p in payload.get("pinned_calibration_ids", [])]
            snr_limit, expected_interval = _rule_inputs(payload)
            # Forward-compat: legacy RunStarted payloads have no
            # conduct_mode key; .get(..., "Conducted") returns the
            # historical default so legacy rows land as Conducted, which
            # is true of every Run started before this field existed.
            conduct_mode = payload.get("conduct_mode", "Conducted")
            # Forward-compat: legacy RunStarted payloads have no
            # external_refs key; .get(..., []) returns [] so legacy rows
            # (and every Conducted Run) land with capture_code IS NULL.
            capture_code = _extract_capture_code(payload.get("external_refs", []))
            await conn.execute(
                _INSERT_RUN_SQL,
                UUID(payload["run_id"]),
                payload["name"],
                UUID(payload["plan_id"]),
                subject_id,
                payload.get("raid"),
                datetime.fromisoformat(payload["occurred_at"]),
                overrides_present,
                campaign_id,
                pinned_calibration_ids,
                snr_limit,
                expected_interval,
                conduct_mode,
                capture_code,
            )
            return
        if event.event_type == "RunResumed":
            # Held -> Running AND reset running_since so the liveness signal
            # measures only the new Running interval, not the time spent Held.
            await conn.execute(
                _UPDATE_RESUMED_SQL,
                UUID(event.payload["run_id"]),
                datetime.fromisoformat(event.payload["occurred_at"]),
            )
            return
        if event.event_type == "RunAddedToCampaign":
            await conn.execute(
                _UPDATE_CAMPAIGN_SQL,
                UUID(event.payload["run_id"]),
                UUID(event.payload["campaign_id"]),
            )
            return
        if event.event_type == "RunRemovedFromCampaign":
            await conn.execute(
                _UPDATE_CAMPAIGN_SQL,
                UUID(event.payload["run_id"]),
                None,
            )
            return
        if event.event_type == "RunAdjusted":
            snr_limit, expected_interval = _rule_inputs(event.payload)
            await conn.execute(
                _UPDATE_ADJUSTED_SQL,
                UUID(event.payload["run_id"]),
                UUID(event.payload["adjusted_by"]),
                snr_limit,
                expected_interval,
            )
            return
        new_status = _EVENT_TO_STATUS.get(event.event_type)
        if new_status is None:
            return
        await conn.execute(
            _UPDATE_STATUS_SQL,
            UUID(event.payload["run_id"]),
            new_status,
        )


__all__ = ["RunSummaryProjection"]
