# Calibration module <span class="md-maturity md-maturity--stable" title="Five slices shipped with three events, polymorphic source union, and Run / Dataset anchoring in place">stable</span>

## Purpose & Scope

The Calibration module records empirical instrument values that downstream consumers need to interpret raw data. A Calibration is the digital record of the kind of number that historically lived in a spreadsheet or a lab-notebook page: "the rotation axis of the Aerotech stage projects to pixel 1024.5 at 25 keV with the 5x optics"; "the Andor's pixel pitch is 6.5 microns with a 1.0x scintillator-detector geometry". Reconstructions, alignment procedures, and operator overrides all need to cite a specific value at a specific operating point.

A Calibration is keyed by the triple `(target_id, quantity, operating_point)` and grows revisions append-only. Each revision carries its own status (Provisional or Verified) and a tagged source (Measured from a Procedure, Computed from a Dataset, or Asserted by an Actor). Earlier revisions stay readable for reproducibility; new revisions may explicitly supersede prior ones on the same calibration.

A Calibration carries five roles:

- **Identity.** The triple `(target_id, quantity, operating_point)` is unique across the system. The aggregate id is the internal opaque handle; the identity triple is what operators and downstream consumers query by.
- **A closed catalog of quantities.** `CalibrationQuantity` is a closed StrEnum. The current set covers `rotation_center`, `detector_pixel_size`, `magnification`, and `effective_thickness`; growth happens by PR, with each quantity declaring its `operating_point_schema` and `value_schema` at import time.
- **Append-only revisions.** New revisions append to the aggregate's ordered list; prior revisions are immutable. Status (Provisional or Verified) is per-revision; the aggregate has no overarching state machine.
- **Polymorphic source provenance.** Each revision tags its origin: `MeasuredSource` cites the Procedure that measured the value, `ComputedSource` cites the Dataset the value was extracted from, and `AssertedSource` cites the Actor who typed it directly. The same Calibration can mix sources across revisions.
- **Anchoring into Run and Dataset.** A Run pins the exact `calibration_id` set it consumed at start, so AsShot reproducibility holds even when later revisions supersede the pinned ones. Datasets in turn record which calibration revisions their reconstruction consumed.

<div class="cora-aside cora-aside--deferred" markdown>

Out of scope
{: .cora-kicker }

- **Refined / three-tier status.** The status ladder ships with two tiers (Provisional, Verified). A `Refined` middle tier is deferred until pilot use surfaces a distinct statistical-maturity window between the two existing tiers.
- **Time-keyed lookup port.** `CalibrationLookup.find_for(asset, quantity, operating_point, as_of)` is deferred. Today's consumers fetch the calibration by id from the Run or Dataset that pinned it.
- **Calibration sets / bundles.** Grouping several calibrations into a named bundle that gets pinned together is deferred. Today's pin is per `calibration_id`.
- **Cross-aggregate supersession.** A revision may only supersede a prior revision on the same calibration. Re-baselining an operating point starts a new Calibration.
- **Cross-BC existence checks on source ids.** `MeasuredSource.procedure_id`, `ComputedSource.dataset_id`, and `AssertedSource.actor_id` are bare references; the write path does not verify the target exists at the time the revision is appended.
- **Per-revision projection.** A `proj_calibration_revisions` read model is deferred. Single-aggregate revision reads go through `GET /calibrations/{id}`, which folds the aggregate's event stream.

</div>

## Aggregates

| Name | Identity | State summary | FSM |
|---|---|---|---|
| `Calibration` | `id: UUID` (with unique triple `(target_id, quantity, operating_point)`) | `target_id`, `quantity`, `operating_point`, `description?`, `revisions` (ordered tuple), `defined_by_actor_id` | no |

The aggregate has no overall lifecycle state. Status lives on the revision, not on the calibration, because a single calibration may carry a Provisional initial guess and a later Verified refinement side-by-side, and a downstream consumer pinning the Provisional revision should remain valid even after a Verified one lands.

Lifecycle bookkeeping timestamps (`defined_at`, `last_revised_at`) do NOT live on the aggregate. They are derived at projection-apply time from each event's envelope `occurred_at` (`defined_at`) or from the revision's domain `established_at` (`last_revised_at`) and surfaced from `proj_calibration_summary`. The `get_calibration` handler returns a `CalibrationView` bundling the aggregate state with the projection-sourced timestamps; the route + MCP DTOs mark both fields nullable since the projection may transiently lag behind the event store. This is the Path C convention used by Method, Plan, Family, and the other FSM-template aggregates.

## Value Objects

| Name | Shape | Where used |
|---|---|---|
| `CalibrationDescription` | trimmed string, 0-2000 chars (optional) | `Calibration.description` |
| `CalibrationRevision` | `revision_id`, `value: dict`, `status`, `source`, `established_at`, `established_by_actor_id`, `decided_by_decision_id?`, `supersedes_revision_id?` | members of `Calibration.revisions` |
| `CalibrationSource` | 3-arm tagged union: `MeasuredSource(procedure_id)` \| `ComputedSource(dataset_id)` \| `AssertedSource(actor_id)` | `CalibrationRevision.source` |

`CalibrationStatus` is a closed two-value enum: `Provisional` (initial estimate or early-data-derived figure; downstream consumers may use it but should know it is unblessed) and `Verified` (blessed for production reconstructions and analyses).

`operating_point` and revision `value` travel as JSON-shaped `dict`s validated STRICT against per-quantity JSON Schemas at the decider. The `additionalProperties: False` discipline and primitive-only property types prevent the calibration aggregate from accidentally turning into a free-form bag. Postgres jsonb canonicalises key order on insert and compares numbers by value (`25 == 25.0`), so the identity-triple uniqueness constraint holds without any application-layer canonicalisation step.

## FSM

N/A. The Calibration aggregate has no load-bearing lifecycle FSM. Revisions accumulate append-only on a slim aggregate; status lives on each revision rather than on the calibration as a whole.

## Events

| Event | Payload sketch | When emitted |
|---|---|---|
| `CalibrationDefined` | `calibration_id`, `target_id`, `quantity`, `operating_point`, `description?`, `defined_by_actor_id`, `occurred_at` | `define_calibration` succeeds (genesis; no revisions yet) |
| `CalibrationRevisionAppended` | `revision_id`, `calibration_id`, `value`, `status`, `source_procedure_id?`, `source_dataset_id?`, `source_actor_id?`, `established_at`, `established_by_actor_id`, `decided_by_decision_id?`, `supersedes_revision_id?`, `occurred_at` | `append_calibration_revision` succeeds |
| `CalibrationRevisionPublished` | `calibration_id`, `revision_id`, `outbound_permit_id`, `signature_envelope_kind`, `signing_version`, `signature_bytes_hex`, `signature_kid`, `receipt_id`, `published_at`, `published_by`, `publication_status`, `occurred_at` | `publish_revision` succeeds; atomically appends a matching `PublicationReceiptRecorded` on the outbound Permit stream. No-op fold on Calibration state today (the publication block on `CalibrationRevision` is deferred). |

`CalibrationRevisionAppended` serialises the polymorphic source as three nullable `source_*_id` fields with exactly one non-null per the exclusive-arc pattern. The wire shape on REST and MCP keeps the nested `{kind, <id>}` envelope for readability; the event payload and projection columns use exclusive-arc to keep storage shape and constraint enforcement direct.

## Slices

| Command | Category | REST | MCP tool | Idempotency |
|---|---|---|---|---|
| `DefineCalibration` | NEW | `POST /calibrations` | `define_calibration` | required |
| `AppendCalibrationRevision` | MODIFIED | `POST /calibrations/{calibration_id}/revisions` | `append_calibration_revision` | required |
| `PublishRevision` | MODIFIED | `POST /calibrations/{calibration_id}/revisions/{revision_id}/publish` | `publish_revision` | required |
| `GetCalibration` | QUERY | `GET /calibrations/{calibration_id}` | `get_calibration` | none |
| `ListCalibrations` | QUERY | `GET /calibrations` | `list_calibrations` | none |

**Errors per slice.** Beyond Pydantic boundary 422s, each slice raises:

`DefineCalibration`
: `InvalidCalibrationQuantity`, `InvalidOperatingPoint`, `InvalidCalibrationDescription`, `CalibrationIdentityAlreadyExists` (the `(target_id, quantity, operating_point)` triple already exists), `Unauthorized`

`AppendCalibrationRevision`
: `CalibrationNotFound`, `InvalidCalibrationValue`, `InvalidCalibrationSource`, `SupersedesRevisionNotFound` (the `supersedes_revision_id` does not match any revision on this calibration), `Unauthorized`, `ConcurrencyError`

`PublishRevision`
: `CalibrationNotFound`, `CalibrationRevisionNotFound`, `CalibrationCannotPublishRevision` (the revision has no `content_hash`), `OutboundPermitNotActive` (no outbound Permit, or the Permit is not `Active`), `Unauthorized`. Returns `201 Created` with `{receipt_id}`; idempotency-wrapped so a retried key returns the cached receipt rather than re-publishing.

`GetCalibration`
: `CalibrationNotFound`

`ListCalibrations`
: (boundary 422 or `Unauthorized` only)

`DefineCalibration` and `AppendCalibrationRevision` are wrapped by the `Idempotency-Key` header pattern. The append path treats idempotency as load-bearing for agent-subscriber callers (a CautionDrafter or RunDebriefer subscriber that retries after a network blip must not produce a duplicate revision).

## Storage & Projections

One read-side table backs the Calibration module today.

```sql title="proj_calibration_summary"
CREATE TABLE proj_calibration_summary (
    calibration_id              UUID        PRIMARY KEY,
    target_id       UUID        NOT NULL,
    quantity                    TEXT        NOT NULL,
    operating_point             JSONB       NOT NULL,
    description                 TEXT,
    defined_at                  TIMESTAMPTZ NOT NULL,
    last_revised_at             TIMESTAMPTZ NOT NULL,
    defined_by_actor_id         UUID        NOT NULL,
    revision_count              INTEGER     NOT NULL DEFAULT 0
        CHECK (revision_count >= 0),
    latest_revision_status      TEXT        CHECK (
        latest_revision_status IS NULL
        OR latest_revision_status IN ('Provisional', 'Verified')
    ),
    latest_revision_source_kind TEXT        CHECK (
        latest_revision_source_kind IS NULL
        OR latest_revision_source_kind IN ('measured', 'computed', 'asserted')
    ),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT proj_calibration_summary_identity_unique
        UNIQUE (target_id, quantity, operating_point)
);
```

The `UNIQUE (target_id, quantity, operating_point)` constraint is the enforcement point for the identity-triple invariant. Postgres jsonb provides value-based equality (key-order normalisation, numeric `25 == 25.0`, duplicate-key dedup) at the storage layer, so two `define_calibration` calls with `{energy: 25, optics_config: "5x"}` and `{optics_config: "5x", energy: 25.0}` resolve to the same row and the second raises `CalibrationIdentityAlreadyExists`.

`latest_revision_status` and `latest_revision_source_kind` are denormalised onto the summary row so `GET /calibrations` filters do not need to join a per-revision table at query time. Both are NULL for a calibration with no revisions yet. A partial index on `(target_id, quantity) WHERE latest_revision_status = 'Verified'` supports the hot read path for reconstruction consumers that want only blessed values.

`GET /calibrations/{id}` reads the aggregate's full event stream and folds it (so every revision is present in the response). `GET /calibrations` reads exclusively from `proj_calibration_summary` with keyset pagination over `(defined_at, calibration_id)` and filters on `target_id`, `quantity`, `latest_revision_status`, and `latest_revision_source_kind`.

## Cross-Module boundaries

| Module | Relationship | What's exchanged |
|---|---|---|
| Trust | gated-by | Every write-side Calibration slice is gated by the Authorize port resolving a `Policy` for the `(principal, command, conduit, surface)` tuple; deny outcomes refuse before the decider runs |
| Equipment | shared-id-with | `Calibration.target_id` references the Asset whose behaviour is being measured (the rotary stage whose rotation centre is tracked, the detector whose pixel pitch is measured) |
| Operation | shared-id-with | `MeasuredSource.procedure_id` references the alignment Procedure whose run produced the value |
| Data | shared-id-with | `ComputedSource.dataset_id` references the Dataset the value was extracted from (`tomopy.find_center_vo` and similar numerical analyses); `Dataset.used_calibration_ids` records the reverse direction |
| Access | shared-id-with | `AssertedSource.actor_id`, `Calibration.defined_by_actor_id`, and each revision's `established_by_actor_id` reference Actors |
| Decision | shared-id-with | `CalibrationRevision.decided_by_decision_id` references the Decision that justified appending the revision (operator pivot, agent advisory); not verified at the write path |
| Run | reads-from | `Run.pinned_calibration_ids` carries an AsShot `frozenset[calibration_id]` set at Run.start that is IMMUTABLE through the rest of the Run's lifecycle; each pinned calibration's latest revision at pin time is the AsShot anchor |

Source-id targets are validated for UUID shape at the API boundary but not for existence at write time, in line with the cross-BC eventual-consistency stance. The `calibration_id` pin on `Run.pinned_calibration_ids` is the AsShot anchor that makes a reconstruction reproducible: the Run's lifecycle freezes the pin set at start, so the calibration set the Run consumed stays citable even as new revisions land.

## Examples

The four examples below follow the canonical path for one Calibration: define an identity, append a Provisional revision from a measurement Procedure, append a Verified revision computed from a Dataset that supersedes the first, and query the projection. The caller's principal becomes `defined_by_actor_id` at definition and `established_by_actor_id` on each revision. For the REST/MCP equivalence, auth, and idempotency conventions these examples share, see [Reading the examples](../index.md) on the Modules landing page.

<!-- extracted from tests/contract/calibration/test_define_calibration.py -->

### Define a Calibration

=== "REST"

    ```http
    POST /calibrations
    Content-Type: application/json
    Idempotency-Key: 6f4a3b1c-8e2d-4f5a-9b8c-1d2e3f4a5b6c
    X-Principal-Id: 11111111-2222-3333-4444-555555555555

    {
      "target_id": "aaaa1111-2222-3333-4444-555555555555",
      "quantity": "rotation_center",
      "operating_point": {
        "energy": 25,
        "optics_config": "5x"
      },
      "description": "Rotation centre for the Aerotech stage on 2-BM at the 5x optics."
    }
    ```

    A successful call returns `201 Created` with the newly-assigned `calibration_id`. The calibration starts with zero revisions; reconstructions cannot pin it until at least one revision is appended.

=== "MCP"

    ```python
    mcp.call_tool(
        "define_calibration",
        {
            "target_id": "aaaa1111-2222-3333-4444-555555555555",
            "quantity": "rotation_center",
            "operating_point": {"energy": 25, "optics_config": "5x"},
            "description": "Rotation centre for the Aerotech stage on 2-BM at the 5x optics.",
        },
    )
    ```

### Append a Provisional revision from a measurement Procedure

=== "REST"

    ```http
    POST /calibrations/<calibration-id>/revisions
    Content-Type: application/json
    Idempotency-Key: 7c8d9e0f-1a2b-3c4d-5e6f-7a8b9c0d1e2f
    X-Principal-Id: 22222222-3333-4444-5555-666666666666

    {
      "value": {
        "center": 1024.5,
        "uncertainty": 0.3
      },
      "status": "Provisional",
      "source": {
        "kind": "Measured",
        "procedure_id": "bbbb1111-2222-3333-4444-555555555555"
      }
    }
    ```

    Returns `201 Created` with the newly-assigned `revision_id`. The calibration's `latest_revision_status` flips to `Provisional` and `latest_revision_source_kind` to `measured`. Reconstructions may now pin this calibration; downstream consumers that filter on `latest_revision_status=Verified` will not see it yet.

=== "MCP"

    ```python
    mcp.call_tool(
        "append_calibration_revision",
        {
            "calibration_id": "<calibration-id>",
            "value": {"center": 1024.5, "uncertainty": 0.3},
            "status": "Provisional",
            "source": {
                "kind": "Measured",
                "procedure_id": "bbbb1111-2222-3333-4444-555555555555",
            },
        },
    )
    ```

### Append a Verified revision computed from a Dataset, superseding the first

=== "REST"

    ```http
    POST /calibrations/<calibration-id>/revisions
    Content-Type: application/json
    Idempotency-Key: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
    X-Principal-Id: 33333333-4444-5555-6666-777777777777

    {
      "value": {
        "center": 1024.72,
        "uncertainty": 0.08
      },
      "status": "Verified",
      "source": {
        "kind": "Computed",
        "dataset_id": "cccc1111-2222-3333-4444-555555555555"
      },
      "supersedes_revision_id": "<provisional-revision-id>"
    }
    ```

    The new revision carries the refined value from `tomopy.find_center_vo` on the first acquisition's projections. The supersession edge points at the prior revision on the same calibration; the prior revision stays readable through `GET /calibrations/{id}` for any Run that pinned it. The summary row's `latest_revision_status` becomes `Verified` and `latest_revision_source_kind` becomes `computed`.

=== "MCP"

    ```python
    mcp.call_tool(
        "append_calibration_revision",
        {
            "calibration_id": "<calibration-id>",
            "value": {"center": 1024.72, "uncertainty": 0.08},
            "status": "Verified",
            "source": {
                "kind": "Computed",
                "dataset_id": "cccc1111-2222-3333-4444-555555555555",
            },
            "supersedes_revision_id": "<provisional-revision-id>",
        },
    )
    ```

### List Verified calibrations for an Asset

=== "REST"

    ```http
    GET /calibrations?target_id=aaaa1111-2222-3333-4444-555555555555&latest_revision_status=Verified
    X-Principal-Id: 11111111-2222-3333-4444-555555555555
    ```

    Returns the page of calibrations on the Aerotech stage whose latest revision is blessed for production. Each item carries `calibration_id`, `target_id`, `quantity`, `operating_point`, `revision_count`, `latest_revision_status`, `latest_revision_source_kind`, `defined_at`, and `last_revised_at`, plus an opaque `next_cursor` for keyset pagination.

=== "MCP"

    ```python
    mcp.call_tool(
        "list_calibrations",
        {
            "target_id": "aaaa1111-2222-3333-4444-555555555555",
            "latest_revision_status": ["Verified"],
        },
    )
    ```

The same query without `latest_revision_status` returns every calibration on the Asset (including those whose latest revision is still Provisional and those with no revisions yet). Reconstruction consumers that want only blessed values pass `latest_revision_status=["Verified"]`; alignment workflows that want the latest measurement of any kind drop the filter.
