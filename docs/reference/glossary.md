# Glossary

For anyone reading CORA. Each term defined once and used the same way in code, commits, and prose. Names are load-bearing; drift in vocabulary is drift in the model. If a page uses a term differently, the page is wrong.

## Project name disambiguation

- **CORA.** This project. The operational system documented in this repository, primarily targeting synchrotron imaging beamlines starting with APS 2-BM. Unqualified `CORA` always refers to this project.
- **IEEE-1872-CORA.** IEEE 1872-2015's main ontology, also named `CORA` (Core Ontology for Robotics and Automation). Direct acronym collision with this project. Always disambiguate as `IEEE-1872-CORA` (or `IEEE 1872's CORA`) in cross-corpus citations to avoid contaminating downstream readers. IEEE 1872-CORA is part of a four-ontology robotics standard (IEEE-1872-CORA + CORAX extensions + RPARTS robot parts + POS position/orientation/pose) built on SUMO, not BFO. It uses an anatomy-as-class plus role-as-subrelation modeling pattern (Pattern B in the role-aggregate-design ternary), distinct from this project's Pattern C role-as-aggregate. See [project_role_aggregate_design](../../../.claude/projects/-Users-dgursoy-Documents-Github-cora/memory/project_role_aggregate_design.md) Lock 16 for the load-bearing rationale.

## Architecture

*BCs, aggregates, deciders, slices, FCIS, ports, kernel.*

- **Bounded context (BC).** A self-contained slice of the domain with its own model, language, API surface. Examples: `access`, `equipment`, `recipe`, `run`, `data`, `decision`, `subject`, `trust`, `agent`, `calibration`.
- **Aggregate.** Consistency boundary inside a BC. Holds state, validates commands, emits events.
- **Decider.** Pure `(state, command) -> events`. Business rules. No I/O.
- **Evolver.** Pure `(state, event) -> state`. Folds events into state.
- **Fold-on-read.** Rebuild aggregate state by replaying events on every command. No snapshots yet.
- **Vertical slice.** One folder per command or query: `command.py`, `decider.py`, `handler.py`, `route.py`, `tool.py`.
- **FCIS.** Functional core / imperative shell. Pure deciders and evolvers; all I/O at the shell via injected ports.
- **Port.** A `Protocol` defining a side-effect seam (clock, ID generator, event store, `Authorize`, idempotency, `TokenVerifier`, `LLM`, `LogbookMirror`).
- **Kernel.** Shared kernel: cross-BC primitives (event envelope, deps wiring, authorize factory, token-verifier registry).
- **Slim vs Lifecycle aggregate.** Two patterns for cheap replay. Slim closes out and starts fresh; Lifecycle carries state across phases.

## Events

*Event store, streams, positions, transactions, projections.*

- **Event store.** Append-only Postgres table of immutable events. INSERT-only at the DB role level.
- **Stream.** All events for one aggregate instance, ordered by version.
- **Position.** Global monotonic ordinal of an event in the store.
- **transaction_id (xid8).** PG18 transaction identifier on every event. Lets projection workers advance a cursor without skipping in-flight inserts.
- **Projection.** A read model built by replaying events into a denormalized table. Workers tail the store and advance a bookmark.

## Surfaces

*REST, MCP, A2A, Surface aggregate.*

- **REST.** FastAPI HTTP endpoints under `/<resource>`. OpenAPI at `/docs`.
- **MCP.** Model Context Protocol, the LLM-agent surface. Streamable HTTP at `/mcp`. Same handler as REST.
- **A2A.** Agent-to-Agent protocol. Planned trust-boundary surface for cross-organization agent calls (deferred).
- **Surface.** *(Trust BC)* Aggregate naming the ingress shape a call arrives through. Closed `SurfaceKind` enum: `HTTP`, `MCP_STDIO`, `MCP_STREAMABLE_HTTP`. `surface_id` threads through every handler, the `Authorize` port, Policy evaluation, and the idempotency cache key namespace (IETF draft-07 §5 composite key).

## Standards

*ISA, ISO/IEC, NIST, PROV-O, RAiD.*

- **ISA-95.** Manufacturing operations hierarchy: Enterprise / Site / Area / Unit / Component / Device. CORA draws the three equipment tiers (Unit / Component / Device) from it for `Asset.tier`; the upper levels (institution / site / area) are facility-envelope scope owned by the Federation `Facility` aggregate, not Asset tiers.
- **ISA-88.** Batch control. Basis for Track A (Method / Practice / Plan / Run).
- **ISA-106.** Continuous-process operations. Basis for Track B.
- **ISA-99 / IEC 62443.** Industrial cybersecurity. Basis for Track C: Zones, Conduits, Policies (`trust` BC).
- **ISO/IEC 42001 + NIST AI RMF.** AI governance frameworks. Inform Decision and Strategy BCs.
- **W3C PROV-O.** Provenance ontology. Borrowed at API boundaries (Activity, Entity, Agent, used, wasGeneratedBy). W3C Provenance Working Group is closed; PROV-O is frozen 2013 bedrock vocabulary, not a moving spec. Community momentum lives in downstream consumers (RO-Crate, FAIRSCAPE).
- **RAiD (ISO 23527).** Research Activity Identifier. Forward-compat field on `RunStarted`.

Watch-only (not adopted as a glossary term, see [Deferred](../stack/deferred.md)):

- **PIDINST.** RDA-WG recommendation for persistent IDs of physical instruments, layered on DataCite Schema 4.5+ via `resourceTypeGeneral=Instrument`. Adoption is thin (HZB at BESSY II is the only confirmed photon-science adopter as of 2026), so CORA treats it as a watch item rather than a standard. The Asset model reserves capacity for a publication-quality persistent ID; the minting profile (PIDINST vs raw DataCite Instrument resourceType vs other) is decided when first needed.

## Authz

*ReBAC, BOLA, Cedar, principal, actor vs profile, bearer-token edge auth.*

- **ReBAC.** Relationship-based access control (planned: SpiceDB or OpenFGA). For multi-stakeholder ownership common in shared facilities.
- **BOLA.** Broken Object-Level Authorization (OWASP API #1). Covered by a parametrized cross-principal contract test on every read endpoint (12 aggregates today).
- **Cedar.** Policy language used in `decision` BC predicates.
- **Principal.** Authenticated identity attached to every command and event envelope. Required in production via `REQUIRE_AUTHENTICATED_PRINCIPAL=true`.
- **Actor vs Profile.** `Actor` is the immutable identity in events; `Profile` is the mutable PII row, separately stored and erasable. GDPR-shaped. `Actor.kind ∈ {human, agent, service_account}`.
- **`Authorize` port.** Single seam: `authorize(principal_id, command_name, conduit_id, surface_id) → AuthzResult`. Exposed on the kernel as `Kernel.authz`. Every command and query passes through it.
- **`TokenVerifier` port.** Edge-auth seam: `verify(token) → VerifiedPrincipal`. Two adapters today — `JwtTokenVerifier` (JWKS, RFC 9068) and `IntrospectionTokenVerifier` (RFC 7662). `IdentityProviderRegistry` routes by `iss` claim.
- **`BearerAuthMiddleware`.** ASGI middleware at the HTTP edge. Reads `Authorization: Bearer`, verifies via `Kernel.token_verifier`, stashes `VerifiedPrincipal` on `request.state.principal`.

## Equipment

*Assets, Families, Affordances. The device-classification side of Equipment BC.*

- **Asset.** A physical equipment instance registered in the equipment tree. Its tier facet is `Asset.tier`, a closed `AssetTier` StrEnum with exactly three values (Unit / Component / Device, the ISA-88 equipment tiers). Belongs to one or more Families. Facility-envelope scope (institution / site / area) is NOT an Asset tier; a root Asset binds its owning `Facility` via `Asset.facility_code`.
- **AssetTier.** A closed `AssetTier` StrEnum with exactly three values: `Unit`, `Component`, `Device`. First-class field: a `register_asset` command field, an `AssetRegistered` payload key, an aggregate-state field, and a projection column. Set once at registration, never mutated. The single-parent tree rule (`parent_id` chain, no cycles) IS structurally enforced; tier ordering between parent and child is NOT. CORA permits Device-in-Device parent chains when the parent is itself an addressable control surface (smart instruments, networked subassemblies that expose their own setpoints). Anchoring rule (XOR, enforced by the `register_asset` decider): a root Asset has `parent_id = None` and binds `facility_code`; a non-root Asset has a `parent_id` and does NOT bind `facility_code`, inheriting facility scope through the parent tree. A beamline (e.g. 2-BM) is a root Asset with `tier = Unit`; sub-systems and devices are nested `tier = Component` or `tier = Device` Assets.
- **Asset two-axis state.** Asset carries two orthogonal state axes: `lifecycle` (`Commissioned` / `Active` / `Maintenance` / `Decommissioned` — is this device part of inventory and assignable) and `condition` (`Nominal` / `Degraded` / `Faulted` — is it actually working right now). The two move independently: a Decommissioned asset can be discovered Faulted on inventory check; an Active asset can be Degraded without being pulled out of service. The split is the deliberate design lock per the asset-condition memo; do not collapse `lifecycle` and `condition` into a single FSM. Matches PI-System asset-health (Good / Warning / Bad) and SEMI E10 productive-vs-unproductive-time orthogonality.
- **Family.** A device-class abstraction: WHAT kind of equipment this is, device-agnostic. Examples: `RotaryStage`, `LinearStage`, `Camera`, `Scintillator`, `Hexapod`, `Mirror`. Earlier this aggregate was named `Capability`; the operations-layer Recipe BC `Capability` aggregate (separate concept; see below) landed 2026-05-18 and took that name over.
- **Affordance.** A closed-enum primitive a Family declares it supports. Two patterns: operational affordances (`-able`/`-ible`/`-ing` suffix per Swift Guidelines, "device supports doing X" or "device performs X"; 28 items mixing 22 `-able`/`-ible` actions with 6 `-ing` role/flow gerunds — `Marking`, `Pulsing`, `Following`, `Leading`, `Recording`, `Capturing`), and lifecycle affordances (noun, "device has lifecycle property X"; 1 item — `Consumable`). Cross-BC contract: at `define_plan` time, the union of every wired Asset's Families' affordances must cover the bound Method's Capability `required_affordances` (otherwise `PlanAffordancesNotSatisfiedError`, 409). See [Affordances reference](affordances.md) for the 29-item v1 list.

## Recipe ladder

*Capability, method, practice, plan, run, logbook.*

- **Capability.** *(Recipe BC)* An operations-layer template declaring WHAT a Method or Procedure can do: `required_affordances` (the Family-affordance contract any binding must cover), `parameters_schema` (the parameter contract Method.parameters_schema must be a subset of), `executor_shapes` (closed v1 enum `{METHOD, PROCEDURE}` — which executor kinds may bind). Distinct from Equipment Family (`what a device IS`); Capability is `what an operation provides`. Methods bind via `Method.capability_id` (REQUIRED); Procedures bind via `Procedure.capability_id` (optional). Namespaced `cora.capability.*` codes; status FSM `Defined → Versioned → Deprecated` with optional `replaced_by_capability_id` (LOINC `MAP_TO` precedent). NOT the same as capability-security capability: CORA uses the industrial-automation sense (a verb the operation provides); the systems-security sense (CHERI, Capsicum, seL4, KeyKOS — an unforgeable token-of-authority bound to a reference and hardware-enforced via nonforgeability/nonbypassability/monotonicity, lineage from Dennis & Van Horn 1966 onward) is structurally incompatible. CORA's token-of-authority analog is the `Authorize` port, which is a separate aggregate. Do not introduce authorization or token-passing semantics on the Capability aggregate.
- **ExecutorShape.** *(Recipe BC, closed v1 StrEnum)* Declares which executor kinds may implement a Capability: `METHOD` (heavyweight science executor producing datasets via Plan → Run) or `PROCEDURE` (lightweight ceremony executor without datasets, ISA-106 atoms). One Capability may declare both shapes.
- **Method.** A reusable technique template. Binds to one Capability via `capability_id` (REQUIRED) and to a set of Equipment Families via `needed_family_ids` (hardware-compat). Method's `parameters_schema` must be a structural subset of the bound Capability's `parameters_schema` (`MethodParametersNotSubsetError`, 409).
- **Practice.** A Method bound to a site or set of Families.
- **Plan.** A Practice bound to specific Assets and a window.
- **Run.** An execution of a Plan. FSM `RunStatus`: `Running`, `Held`, `Completed`, `Aborted`, `Stopped`, `Truncated`.
- **Logbook.** Append-only narrative log on a Run or Decision. Used for OTel `gen_ai.*` reasoning entries on Decisions.

## Agents

*Agent BC, RunDebriefer, CautionDrafter.*

- **Agent.** *(Agent BC)* Config-only aggregate naming a configured LLM agent: `kind` (free-form `AgentKind`), `name`, `version`, `model_ref`, `prompt_template_id`, `capabilities`, `tools`, `budget`. FSM `Defined → Versioned ⇄ Suspended → Deprecated`. `Agent.id` is shared with Access BC's `Actor.id` for the same agent (cross-BC atomic via `EventStore.append_streams`; every Agent.id is also an Actor.id with `kind="agent"`).
- **RunDebriefer.** First registered Agent. Subscribes to terminal Run events; proposes a debrief entry via the `LLM` port; result lands in the Run logbook.
- **CautionDrafter.** Second registered Agent. Subscribes to terminal Run events; proposes a Caution (5-choice enum: NoAction / ProposeNotice / ProposeCaution / ProposeWarning / ProposeSupersede) and promotes via `promote_caution_proposal` (writes Caution BC events directly via `EventStore.append_streams`).
- **Debrief lease.** *(Agent BC subscriber pattern)* Cross-agent coordination primitive for terminal-Run-event subscribers (RunDebriefer, CautionDrafter, every future agent that LLM-debriefs a Run). Each subscriber appends a `DecisionDebriefRequested` event to the Run stream BEFORE invoking its LLM, using the existing `UNIQUE(stream_type, stream_id, version)` optimistic-concurrency primitive. First writer wins; losers emit a `DebriefConflicted` / `CautionDraftConflicted` audit Decision on their own Decision stream and exit with zero LLM cost. The lease event_id is `uuid5(run_id, f"lease:{terminal_event_id}:{agent_id}")` so per-agent retries are idempotent (same event_id collides) while cross-agent inserts compete on stream version (distinct event_ids, same expected_version). The lease event is audit-only with a no-op Run-evolver fold; it carries no authorization semantic and does not extend `Trust.Policy`.

## Calibration

*Calibration BC, AsShot anchor, pinned vs used.*

- **Calibration.** *(Calibration BC)* Aggregate carrying empirically-measured system constants (motor sensitivities, beam profiles, encoder offsets). Distinct from `operation/calibration` ceremonies — Operation runs the ceremony, Calibration stores the resulting values.
- **AsShot anchor.** Snapshot of which Calibrations were in force at a given moment. `Run.pinned_calibration_ids` captures the Calibrations pinned at `start_run`; `Dataset.used_calibration_ids` captures which of those the resulting Dataset actually consumed. The pair separates "what was available" from "what was used," which the analysis chain needs for provenance.

## Supply

*Supply BC, continuous resources, kind discriminator.*

- **Supply.** *(Supply BC)* Continuous resource a Run or Procedure depends on. Multiple aggregate instances at runtime, one per resource type. Free-form `kind` field (string, NOT closed enum in v1) carries the resource identity. FSM: `Unknown → Available → Degraded → Unavailable → Recovering → Available`; terminal `Decommissioned` via `deregister_supply`. Pre-flight gate: `start_run` / `start_procedure` reject if any `Method.needed_supplies` kind has zero `Available` in scope.
- **Supply.kind.** Free-form identifier covering both upstream-provided and facility-distributed resources, facility-neutral across photon / neutron / FEL / HPC. Starter vocabulary spans photon-facility examples (`photon_beam`, `cryogen`, `vacuum`, `electricity`, `compressed_air`, `process_gas`) and non-photon examples (`neutron_flux`, `FELPulses`, `ComputePool`). Physical infrastructure delivering the resource (gas cabinets, compressors, mass-flow controllers) stays as Equipment Assets; the resource itself is Supply. Promotion to a closed `SupplyKind` enum is deferred until pilot vocabulary settles (2026-05-30 audit watch item).

## Federation

*Federation BC, cross-facility per-edge grants.*

- **Federation.** *(Federation BC, 16th BC)* Cross-facility per-edge trust layer. Distinct from Trust BC (which carries intra-facility command-level PDP rules); Federation carries directional bilateral grants between facilities. Corpus-validated against TUF, Sigstore, SCITT, OAuth RFC 8707, TEFCA QHIN, SWIFT RMA. Reuses `Trust.Surface` for federation-tier identity rather than carving its own.
- **Credential.** *(Federation BC)* Facility-neutral identity record mapping to OAuth/OIDC tokens cross-industry. Identity tuple `(facility_id, audience, purpose)` per RFC 8707; rotation lifecycle handles credential refresh.
- **Permit.** *(Federation BC)* Directional bilateral grant: `Outbound` (this facility permits another to call inbound) or `Inbound` (this facility accepts calls from another). Polymorphic terms per direction; keyed on `(peer_facility_id, audience, purpose)`. Distinct from `Trust.Policy` (intra-facility, undirected, command-level PDP) by layer and shape.
- **Seal.** *(Federation BC)* Per-facility singleton freshness pointer. Metaphor-only naming (avoids TUF-specific jargon like "snapshot" or "timestamp") so the concept travels cleanly across the SCITT / TUF / Sigstore / SWIFT corpus.

## Enclosure

*Enclosure BC, observation-axis-only facility-safety envelope.*

- **Enclosure.** *(Enclosure BC, 17th BC)* Facility-safety envelope (hutch, cabin, cave, vault) whose access-permitted state gates whether dependent Runs and Procedures may start. Observation-axis-only by charter: CORA records the externally-observed permit status, never asserts or commands it. Two orthogonal axes: `permit_status` (`Permitted` / `NotPermitted` / `Unknown`) carries the live observation; `lifecycle` (`Active` / `Decommissioned`) carries terminal retirement. No `Bypassed` state; bypass concerns belong to the upstream interlock system, not the spine.
- **EnclosurePermitStatus.** *(Enclosure BC, closed StrEnum)* Closed enum: `Permitted`, `NotPermitted`, `Unknown`. Updated only via the `observe_enclosure_status` slice (Monitor-trigger), never via an operator `mark_*` command. `Unknown` is the genesis value at `register_enclosure` and the safe fallback when the upstream observer is unreachable.
- **EnclosureLookup port.** *(Enclosure BC)* Cross-BC query port consumed by `start_run` and `start_procedure` pre-flight gates. Returns the current permit status for enclosures covering a Run or Procedure's Asset scope. An empty referencing-Enclosure set passes the gate trivially (Permit-by-default) and raises neither error. When the set is non-empty, the gate rejects with `RunRequiresPermittedEnclosureError` / `ProcedureRequiresPermittedEnclosureError` when EVERY referencing Enclosure fails the Permitted-and-Active check, and `RunEnclosureCoverageMismatchError` / `ProcedureEnclosureCoverageMismatchError` when the set is MIXED (at least one passes, at least one fails). Ships today with both an `InMemoryEnclosureLookup` (used in tests) and a `PostgresEnclosureLookup` production adapter reading through `proj_enclosure_summary`; the upstream EPICS / P4P / Tango observer adapters that drive the projection are deferred to first pilot integration.
