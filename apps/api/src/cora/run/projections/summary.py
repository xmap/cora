"""RunSummaryProjection: folds the Run aggregate's lifecycle events
into the `proj_run_summary` read model that backs `GET /runs`.

Subscribed events (genesis + 6 lifecycle transitions + 2 cross-
aggregate membership transitions + 1 attribution-stamping
transition):
  - RunStarted             -> INSERT (status=Running, name + plan_id +
                                      subject_id? + raid? + running_since +
                                      override_parameters_present +
                                      campaign_id? +
                                      pinned_calibration_ids from payload)
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
  - RunAdjusted            -> UPDATE last_adjusted_by = $2
                              (overwrite-on-each-adjust; mirrors the
                              aggregate-state attribution-half per
                              [[project_fold_symmetry_design]])

All branches idempotent. Genesis-event payload values (plan_id,
subject_id, raid, override_parameters_present, pinned_calibration_ids)
land on INSERT and never change (AsShot invariant for
pinned_calibration_ids); lifecycle UPDATEs only touch `status`;
membership UPDATEs only touch `campaign_id`.

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
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime
from uuid import UUID

from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection.handler import ConnectionLike

_INSERT_RUN_SQL = """
INSERT INTO proj_run_summary
    (run_id, name, plan_id, subject_id, raid, status, created_at, running_since,
     override_parameters_present, campaign_id, pinned_calibration_ids)
VALUES ($1, $2, $3, $4, $5, 'Running', $6, $6, $7, $8, $9::uuid[])
ON CONFLICT (run_id) DO NOTHING
"""

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

_UPDATE_LAST_ADJUSTED_BY_SQL = """
UPDATE proj_run_summary
SET last_adjusted_by = $2, updated_at = now()
WHERE run_id = $1
"""

_EVENT_TO_STATUS = {
    "RunHeld": "Held",
    "RunCompleted": "Completed",
    "RunAborted": "Aborted",
    "RunStopped": "Stopped",
    "RunTruncated": "Truncated",
}


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
            await conn.execute(
                _UPDATE_LAST_ADJUSTED_BY_SQL,
                UUID(event.payload["run_id"]),
                UUID(event.payload["adjusted_by"]),
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
