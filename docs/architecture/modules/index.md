# Modules

Each module is a bounded area of CORA's domain with its own aggregates, events, and slices. Every module page follows the same shape: purpose, maturity, aggregates, value objects, FSM, events, slices, storage, cross-module boundaries, and runnable examples.

<div class="cora-aside" markdown>

- **Two surfaces, same behavior.** Every slice exposes a **REST** path for human operators and integration callers (hit it with `curl`, `httpx`, `HTTPie`, or any HTTP client) and an **MCP** tool for agent callers via the Model Context Protocol SDK. The MCP tool name matches the slice verb, and the argument keys mirror the REST JSON body 1-to-1. Same payload, same errors, same events: pick whichever fits the caller.
- **Auth.** Every call carries the calling actor's identity. In bearer mode (`IDENTITY_PROVIDERS` configured) the same `BearerAuthMiddleware` verifies tokens for both REST and MCP streamable-HTTP, with audience bound per Surface; in legacy mode an `X-Principal-Id: <uuid>` header from a verifying proxy carries it instead. Either way, REST and MCP land on the same `principal_id` at the handler. See the [Auth page](../../stack/auth.md).
- **Idempotency.** Slices marked *required* in the Idempotency column of each module's Slices table accept an `Idempotency-Key: <uuid>` header. Resending the same key with the same body returns the cached response, so operator retries after network blips are safe.

</div>

## Cross-module relationship vocabulary

The **Cross-Module boundaries** table on each module page uses a fixed set of verbs to classify the coupling. Anything not in this table is something the decider does not check at write time.

| Verb | Meaning |
|---|---|
| `gated-by` | A port owned by the other module sits in front of every write slice and can refuse the command. Used for Trust's `Authorize` port. |
| `reads-from` | This module's handler loads state from the other module's read model or aggregate at write time, but never writes to it. |
| `writes-to via append_streams` | A single command emits events into both streams atomically in one Postgres transaction (cross-aggregate write). |
| `shared-id-with` | An id field references the other module's aggregate. Validated for UUID shape at the API boundary, not for existence at write time. |
| `shared-enum-with` | This module references a closed enum owned by the other (no instance link). |
| `depends-on` / `depends-on-kind` | This module references a type-level value (`Family.id`, `Supply.kind` string) owned by the other. `depends-on-kind` marks the kinds-not-ids variant. |
| `upstream-of` / `upstream-of-kind` | Inverse of `reads-from` / `depends-on-kind`. Used when the row sits on the producer's page describing a downstream consumer. |
| `targeted-by` | The other module holds a polymorphic target reference (e.g. `Caution.target = AssetTarget(asset_id=...)`) pointing at this module. |
| `aligns-with` | No schema link today, but the two aggregates belong in the same conceptual frame and a reader should know they sit side by side. |

## Pages

<div class="grid cards" markdown>

-   :material-play-circle-outline:{ .lg .middle } __Run__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Execution layer of the recipe ladder. One Run is one execution instance with a closed FSM, parameter resolution, reading logbook, and cross-module anchors to Plan, Subject, Asset, Clearance, Campaign, and Calibration.

    [Read →](run/index.md)

-   :material-shield-check-outline:{ .lg .middle } __Safety__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Formal regulatory clearances that gate work. ESAF, SAF, A-form, DUO, ESRA, ERA, PLHD, DOOR, BTR, and Form 9 lifecycles, with multi-step review chains and cross-module coverage queries.

    [Read →](safety/index.md)

-   :material-alert-circle-outline:{ .lg .middle } __Caution__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Operator-authored tribal-knowledge notes. Lightweight three-state lifecycle, supersession-as-edit, non-blocking banners at Run.start. Distinct from Safety: never gates work, no review board.

    [Read →](caution/index.md)

-   :material-target-variant:{ .lg .middle } __Calibration__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Empirical instrument values keyed by `(asset, quantity, operating_point)`. Append-only revisions, per-revision status, polymorphic source (Measured / Computed / Asserted), AsShot pinning into Run and Dataset.

    [Read →](calibration/index.md)

-   :material-robot-outline:{ .lg .middle } __Agent__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Typed configuration for AI agents (RunDebriefer, CautionDrafter). Four-state lifecycle with Suspended pause, shared id with Access Actor, MCP tool allowlist, declarative budgets, and two cross-BC action slices.

    [Read →](agent/index.md)

-   :material-folder-multiple-outline:{ .lg .middle } __Campaign__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Operator-declared coordinated study container above Run. Series, sweep, coordinated, or scheduling-block intent, five-state lifecycle with operator hold, atomic two-stream membership writes, and an open-status-default list view.

    [Read →](campaign/index.md)

-   :material-cog-play-outline:{ .lg .middle } __Operation__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Episodic operational tasks: bakeout, characterization, alignment, recovery. Five-state Procedure FSM with truncate for retroactive cleanup, polymorphic per-step entries (setpoint, action, check), and optional binding as a Phase-of-Run.

    [Read →](operation/index.md)

-   :material-water-pump:{ .lg .middle } __Supply__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Continuously-available resources (photon beam, LN2, compressed air, electrical power, vacuum). Five-state availability FSM with Phoebus-style latched recovery, typed `(facility_code, containing_asset_id, kind, name)` address with cross-BC bindings to the Federation Facility + Equipment Asset hierarchies, and operator-asserted transitions today.

    [Read →](supply/index.md)

-   :material-account-key-outline:{ .lg .middle } __Access__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Foundation BC for principal identity: one aggregate (`Actor`), <!-- arch:count kind=event bc=access spell=true -->two<!-- /arch:count --> events, two-state lifecycle, shared identity with `Agent`. The "who you are" layer that every other module references when attributing an event.

    [Read →](access/index.md)

-   :material-wrench-outline:{ .lg .middle } __Equipment__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    <!-- arch:count kind=aggregate bc=equipment spell=true cap=true -->Seven<!-- /arch:count --> aggregates (<!-- arch:bc-aggregates bc=equipment case=type -->`Family`, `Model`, `Assembly`, `Fixture`, `Asset`, `Frame`, `Mount`<!-- /arch:bc-aggregates -->), four-state Asset lifecycle, three-state condition orthogonal to lifecycle, a three-tier intrinsic Asset tree (`Unit`/`Component`/`Device` via `AssetTier`) bound to its owning Facility by `facility_code`, settings-schema validation against the Family-declared Capability, and typed ports for wiring devices into Plans.

    [Read →](equipment/index.md)

-   :material-book-open-page-variant-outline:{ .lg .middle } __Recipe__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    <!-- arch:count kind=aggregate bc=recipe spell=true cap=true -->Four<!-- /arch:count --> aggregates of the abstract-to-bound recipe ladder: <!-- arch:bc-aggregates bc=recipe case=type -->`Capability`, `Method`, `Practice`, `Plan`<!-- /arch:bc-aggregates -->. ISA-88 General/Site/Master/Control recipe progression; the "what we plan to do" layer above Run.

    [Read →](recipe/index.md)

-   :material-shield-lock-outline:{ .lg .middle } __Trust__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    ISA-99/IEC-62443 topology of `Zone`, `Conduit`, `Surface`, `Policy`, `Visit`. Pure Policy Decision Point; Authorize port gates every write-side decider in CORA; first concrete entries-table observation logbook for per-decision audit.

    [Read →](trust/index.md)

-   :material-cube-outline:{ .lg .middle } __Subject__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    One aggregate, seven-state lifecycle with three terminal dispositions, mount/dismount cycle, Asset-lifecycle guard on mount, generic across science domains (materials samples, biological specimens, manufactured parts, astronomical targets, computational subjects).

    [Read →](subject/index.md)

-   :material-database-outline:{ .lg .middle } __Data__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Five aggregates across a dataset's life: `Dataset` (logical content identity, Trial / Production / Retracted intent, lineage edges, AsShot calibration citation), `Distribution` (byte-copies at storage Supplies, DCAT-3 shaped, four-state availability FSM), `Attestation` (recorded checksum / format / bit-rot fact-chain that flips Distribution status), `Edition` (citable, sealable, DOI-mintable publication packages, four-state FSM), and `Acquisition` (the birth-certificate fact linking a producing Asset and Run to the Dataset it captured).

    [Read →](data/index.md)

-   :material-scale-balance:{ .lg .middle } __Decision__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    One aggregate, atomic-immutable for decision facts, `parent_id` chains for corrections, appeals, supersessions, and invalidations. PROV-AGENT-aligned field names, ISO 17025 `decision_rule` citation, operator rating accrual channel.

    [Read →](decision/index.md)

-   :material-link-variant-outline:{ .lg .middle } __Federation__ <span class="md-maturity md-maturity--beta">beta</span>

    ---

    Cross-facility data flows: peer-facility identity (`Facility`), flow authorization (`Permit`), secret-material binding (`Credential`), and per-facility registry-head signing (`Seal`). Trust gates who may act inside the facility; Federation gates what crosses the boundary.

    [Read →](federation/index.md)

-   :material-lock-alert-outline:{ .lg .middle } __Enclosure__ <span class="md-maturity md-maturity--alpha">alpha</span>

    ---

    Permit-status observation for spaces that gate experiments (hutches, sample-prep cabinets, instrument vaults). Three-state status (`Permitted`, `NotPermitted`, `Unknown`) driven only by monitor-side observations, plus an orthogonal operator-driven decommission lifecycle. Sibling to Supply.

    [Read →](enclosure/index.md)

</div>
