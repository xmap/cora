# Conventions

*Identifiers, units of measurement, personal data, schema-validated values, documentation.*

Cross-cutting shapes that recur in every BC. Each family below has one chosen pattern and a short list of anti-patterns that the codebase has settled on. Adopt the pattern when adding a field of that shape; deviate only with a reason.

## Identifiers

Every aggregate gets an opaque internal id at creation. External publication-quality identifiers (DOI, Handle, ORCID, ROR) are minted lazily, only when an outside system needs to cite the entity.

- **Internal id**: UUIDv7 produced by `IdGenerator` port. Carried on every event payload and used as the stream id. Stable for the lifetime of the aggregate, never reused.
- **External id slot**: nullable `external_id: str?` (or a typed `external_refs` map for entities that can carry several) on the aggregate, populated by a later transition event when the external mint succeeds.
- **No coupling**: domain logic never depends on the external id being present. A Run can complete, a Dataset can be archived, a Subject can be discharged without ever being assigned a DOI.

Per-entity scheme map below; the scheme is a docs and adapter concern, not a domain concern. The aggregate carries an opaque string and the namespace of the publishing system.

| Aggregate | External scheme | Authority | Notes |
| --- | --- | --- | --- |
| `data.dataset` | DataCite DOI | DataCite | Kernel 4.6 metadata profile |
| `subject.subject` | IGSN | IGSN through DataCite | Since 2022 an IGSN is a DataCite DOI |
| `equipment.asset` | PIDINST | DataCite or ePIC Handle | Scheme picked when the first asset is cited externally |
| `access.actor` | ORCID iD | ORCID | Separate registry, not a DOI |
| `decision.decision` | none today | n/a | Internal id sufficient until cross-system citation appears |

Cross-entity links between externally published entities use the publishing system's own relationship vocabulary at the export adapter (DataCite `relatedIdentifier`, PROV-O `wasDerivedFrom`). The in-domain reference stays a plain UUID.

**Anti-patterns:**

- Do not use an external identifier as the primary key. Mint timing slips, schemes get renamed, and the cost of changing an aggregate's identity is high.
- Do not block aggregate creation on external mint. A network failure on the mint side should never prevent a Subject from being registered or a Run from starting.
- Do not embed the scheme in the value (`"doi:10.1234/abc"`). Carry the namespace separately so the value stays opaque to the namespace.

## Units of measurement

Numeric fields whose meaning depends on a unit carry the unit as a three-field annotation on the declaring JSON Schema, not in the field name. The annotation is `{system, code, label?}`.

```json
{
  "type": "object",
  "properties": {
    "energy": {
      "type": "number", "minimum": 5.0, "maximum": 35.0,
      "unit": {"system": "udunits", "code": "keV"}
    },
    "exposure": {
      "type": "number", "minimum": 0,
      "unit": {"system": "udunits", "code": "ms", "label": "milliseconds"}
    },
    "start_position": {
      "type": "number",
      "unit": {"system": "udunits", "code": "mm"}
    }
  }
}
```

- **`system`**: namespace identifier; `udunits` for beamline-native fields, `ucum` for clinical, `qudt` for linked-data export, `iec61360` for Industry-4.0 partners. Closed allowlist enforced by `cora.shared.json_schema_validation`.
- **`code`**: the unit token interpreted within `system`. Opaque to anyone outside that namespace.
- **`label`**: optional human display string for codes that are not self-explanatory.

The schema-declared unit is the canonical wire-and-storage unit. Deciders, events, projections, and API responses always carry the value in that exact unit. Conversion happens only at the edge: the NeXus writer adapter flattens to the single `units` string the file format expects; the EPICS reader adapter wraps the legacy `EGU` string back into the annotation shape on the way in; the UI display layer may convert to a per-user preferred unit when that table exists.

**Anti-patterns:**

- Do not put units in field names. `start_position`, not `start_position_mm`; `energy`, not `energy_kev`. The whole point of the annotation is to escape the lock-in that field suffixes create.
- Do not add a `display_unit` second slot on the schema. Display is a per-user concern at the UI edge, not a schema concern.
- Do not convert units inside deciders, evolvers, or projections. The domain ring carries one unit per field.
- Do not change the `system` or `code` of an existing field by editing the schema in place. Emit a new schema version and let downstream rebuild against it (the [forward-only migration policy](workflow.md) applies).

## Personal data

Personal data on Actors lives in a separate mutable `actor_profile` table, not in events. Events carry `actor_id` only. Erasure scrubs the row before deleting it (`UPDATE ... SET name = ''` then `DELETE`) so the dead-tuple bytes carry no PII before VACUUM.

- **Actor aggregate state** holds `id` and `active`; no `name`, no `email`. The event payloads carry the same fields.
- **`actor_profile` table** holds `actor_id PRIMARY KEY`, `name`, optional contact fields, `created_at`, `updated_at`. Written in the same transaction as `ActorRegistered`. The table has `FORCE ROW LEVEL SECURITY` enabled so even superuser sessions go through the policy.
- **Load path** left-joins `actor_profile` and falls back to `<deleted user>` when the row is absent.
- **`forget_actor` slice** scrubs-then-deletes the profile row and emits `ActorProfileForgotten(actor_id, occurred_at)` in a single transaction. The audit event carries no personal data.

The same pattern applies to any future field that may contain personal data: add it as a nullable column on `actor_profile`, or stand up a parallel vault table when the new field belongs to a different aggregate. The infrastructure is one table, not a key-management system.

**Anti-patterns:**

- Do not put personal data in event payloads. Events are immutable; personal data must be deletable.
- Do not encrypt-and-throw-away-the-key (the crypto-shredding pattern). Regulators increasingly treat encrypted personal data as still personal data, and the operational complexity is high for no real benefit when a simple delete is available.
- Do not assume free-text fields are safe from personal data. Reason strings on transition events may contain names or contact details by accident; convention is to either route the free-text through the vault or mark the field as may-contain-personal-data so future erasure tooling knows to check.

## Schema-validated values

One aggregate declares a JSON Schema; another aggregate carries a dict of values validated against it at write time. Two domain families share one implementation, with two deliberately distinct vocabularies.

| Family | Declarer | Carrier | Domain meaning |
| --- | --- | --- | --- |
| Settings | `capability.settings_schema` | `asset.settings` | Slow-moving equipment configuration: pixel offsets, motor calibration values, vendor-specific tuning |
| Parameters | `method.parameters_schema` | `plan.default_parameters` and `run.effective_parameters` | Per-experiment variables: energy, exposure, sample position |

The vocabularies are not interchangeable. "Settings" maps to PLC and SCADA vocabulary and lifecycle; "parameters" maps to recipe and process-control vocabulary. Operators expect both terms in their respective contexts; CORA keeps both.

The shared infrastructure lives in `cora.shared.json_schema_validation` and exposes two functions:

- `validate_schema_declaration(schema, *, error_class)` runs on the declarer's write path. Rejects schemas that are missing or that have the wrong `$schema`, use a forbidden keyword (`$ref`, `oneOf`, `allOf`, conditionals), or fail to compile.
- `validate_values_against_schema(values, schema, *, error_class, no_schema_message)` runs on the carrier's write path.

Each BC keeps its own typed error class (`InvalidCapabilityParametersSchemaError`, `InvalidMethodParametersSchemaError`, `InvalidAssetSettingsError`, `InvalidPlanDefaultParametersError`, `InvalidRunParametersError`) and passes it into the shared validator. Each maps to HTTP 400 via the BC's own route. Different classes mean log aggregators can identify the source BC without parsing message text.

**Strict-by-default posture:** the carrier's validator follows a four-cell table that all instances share.

| schema | values | result |
| --- | --- | --- |
| absent | empty | accept (trivially valid) |
| absent | non-empty | reject with operator guidance |
| present | empty | accept (no required-field check at this layer) |
| present | non-empty | compile and validate; reject on first violation |

Operators wanting "this Capability or Method genuinely has no values to constrain" declare an empty `{}` schema explicitly. The implicit "no schema, anything goes" path is closed by design.

**Anti-patterns:**

- Do not inline schema validation in slices. Always go through the shared validator with a BC-specific error class.
- Do not let carriers fall back to "accept anything" when the declarer's schema is absent. The strict-by-default posture catches the common operator mistake of writing values before declaring how they should be shaped.
- Do not collapse the settings and parameters vocabularies into one name. They are two domain families that happen to share an implementation; the names carry the lifecycle distinction.
- Do not extend the JSON Schema subset to allow `$ref`, `oneOf`, `allOf`, or conditionals without adding the corresponding evolver and projection support. The constrained subset is what lets the declarer's schema be stored, evolved, and rebuilt deterministically.

**Forward-compatible discipline.** `capability.settings_schema` is the strongest candidate to travel between facilities once a publish-pull artifact registry lands. Authoring discipline today avoids a rename pass later. The rules are borrowed from Linux Device Tree bindings: describe the hardware, not the driver; close the schema; reserve namespace expansion slots.

- **Close the schema at every object level.** Set both `additionalProperties: false` and `unevaluatedProperties: false`. Unknown fields are a contract break, not a quiet extension point. A facility that pulls a foreign Capability must fail loudly on a property it does not recognize.
- **Vendor-prefix vendor-specific extensions only.** Properties shared across all instances of the equipment family (`encoder_resolution_deg`, `pixel_pitch_um`) stay generic. Properties that are vendor-specific go under a dotted vendor namespace (`aerotech.servo_gain`, `andor.read_mode`). The generic form is reserved for cross-vendor consensus; do not invent generic names that one vendor's quirk currently occupies.
- **Describe the hardware, not the driver.** Property descriptions name the physical quantity, range, and unit. They do not reference Python classes, EPICS PV names, Tango device URIs, ophyd-async Devices, or any other transport. The same schema must serve an APS-EPICS Capability and a MAX-IV-Tango Capability without edits.
- **Reserve `compatible` and `backend` as property names.** Do not use either name for unrelated purposes in current schemas. They are the documented expansion slots for future cross-facility Asset Integration Manifests.

These rules cost nothing at write time and apply equally to `method.parameters_schema` for the same reason.

## REST URL paths

URL path segments use kebab-case. Hyphens, not underscores, separate words inside a literal segment.

```
GOOD: POST /assets/{asset_id}/add-family
BAD:  POST /assets/{asset_id}/add_family

GOOD: POST /clearances/{clearance_id}/start-review
BAD:  POST /clearances/{clearance_id}/start_review
```

Path parameter placeholders (`{asset_id}`, `{clearance_id}`, `{visit_id}`) keep snake_case because FastAPI binds them to Python function arguments, which follow PEP 8.

Python handler function names, slice directory names, and command class names are unaffected by this rule. They stay PEP 8 (`post_assets_add_family`, `add_asset_family/`, `AddAssetFamily`). The convention only governs the literal URL strings that external API consumers and OpenAPI specifications see.

An architecture fitness test in `apps/api/tests/architecture/test_rest_url_kebab_case.py` enforces this across every slice's `route.py`.

### URL paths and slice/command/MCP names are independent conventions

Slice directory names, command class names, and MCP tool names carry the SUBJECT in the verb-phrase when the slice mutates a specific aggregate kind: `add_asset_family`, `decommission_asset`, `enter_asset_maintenance`, `update_asset_settings`. Reading aloud, "add asset family" and "enter asset maintenance" are parallel English noun-phrases.

URLs use the BARE verb when the path scope already implies the subject. Sibling endpoints under `/assets/{asset_id}/` all follow this shape: `/activate`, `/decommission`, `/relocate`, `/degrade`, `/fault`, `/restore`, `/enter-maintenance`, `/exit-maintenance`, `/add-family`, `/remove-family`. The `/assets/{asset_id}/` segment is the subject; repeating it in the verb (`/enter-asset-maintenance`) would be redundant.

```
GOOD: slice = enter_asset_maintenance/, command = EnterAssetMaintenance,
      MCP tool = enter_asset_maintenance,
      URL = POST /assets/{asset_id}/enter-maintenance
BAD:  URL = POST /assets/{asset_id}/enter-asset-maintenance  (subject duplicated with path scope)
```

The two conventions cover different audiences: code-side names live alongside siblings in the slice directory and need the subject for grep + read-aloud clarity; URL paths live alongside their sibling endpoints under the resource path and stay terse so the path reads as a sentence.

### Multi-segment action paths

When an endpoint manipulates a sub-resource on its parent, the URL nests as `/{parent-id}/{sub-resource}/{verb}`. Examples: `POST /visits/{visit_id}/surface-control/take`, `POST /visits/{visit_id}/surface-control/release`, `POST /federation/seals/{facility_id}/pointer/sign`, `POST /federation/seals/{facility_id}/online-key/rotate`. The noun-resource segment groups related actions; the verb terminates the path.

This nesting is reserved for sub-resources that have multiple actions or own a meaningful name independent of the parent. Single-action endpoints stay flat (`POST /visits/{visit_id}/arrive`).

Multi-word verb-prep URL segments are banned. `take-control-of-surface` was the sole example before commit `bda0d49f1` flipped it to `surface-control/take`; the noun-then-verb shape is the standard.

## Code identifier carve-outs

The field-shape patterns below are deliberate departures from rules that hold elsewhere. Each has a domain reason; each is enforced by an architecture fitness test so a future rename does not undo the carve-out by accident.

### Boolean fields use bare adjectives

The shape is `<adjective>: bool`, not `is_<adjective>: bool`. Aggregate-state and event-payload examples follow this directly: `Caution.propagate_to_children`, `Seal.rotate_seal_online_key.signed_by_offline_root`, `Procedure.conduct_procedure.succeeded`. DTO-side examples follow the same shape (`incomplete` on the `list_permissions` and `get_asset_integration_view` response DTOs). The reader's "is" comes from the field-access read-aloud (`caution.propagate_to_children` reads as "the caution propagates to children"), not from a prefix that doubles the verb.

The `is_`/`has_`/`can_` prefix style is reserved for derived predicates (computed properties or helper methods that ask a yes-no question). `Permit.is_active` is the canonical example: a function `def is_active(state: Permit) -> bool` computes whether the Permit is currently active by inspecting the FSM state. The prefix style does not migrate onto stored field declarations.

### Cannot-transition errors are per-verb, not collapsed

When an aggregate exposes multiple verbs that all reject from the same source-state set (`activate`, `decommission`, `relocate`, `enter_maintenance`, ...), each verb gets its OWN cannot-transition error class. The shape is `<Aggregate>Cannot<Verb>Error`, not a single `<Aggregate>CannotTransitionError` keyed on a `requested_transition: str` field. Asset and Visit are the canonical references: `AssetCannotActivateError` / `AssetCannotDecommissionError` / `AssetCannotEnterMaintenanceError` / `AssetCannotExitMaintenanceError` (asset state.py) and `VisitCannotTakeControlError` / `VisitCannotReleaseControlError` (visit state.py) follow the pattern with detailed docstrings.

The collapsed shape was tried under the name `VisitCannotTransitionError` and split per-verb in commit `ce66d203c`. The verb name in the class IS the diagnostic: `try: ... except AssetCannotActivateError:` reads better than `if e.requested_transition == "activate": ...`, and handler-side mapping to HTTP 409 keys off `isinstance`, not a string field. The transition-name string is duplicate information the call site already knows.

Carve-out: when the aggregate has only ONE such verb (and no foreseeable second), a bare `<Aggregate>CannotTransitionError` is acceptable. Promote to per-verb the moment a second transition slice lands.

### Supply uses `Marked<Status>` for operator-driven transitions

Event classes follow `<Aggregate><PastParticiple>` everywhere except Supply's operator-observation events: `SupplyMarkedAvailable`, `SupplyMarkedUnavailable`, `SupplyMarkedRecovering`. The `Marked` prefix encodes the audit distinction "operator observation, not monitor measurement" that motivates Supply's 5-state FSM. A future automated monitor would emit bare past-participle events (`SupplyObservedAvailable`, `SupplyObservedRecovering`); the prefix is the discriminator.

### Run cross-aggregate edits use `*To*` / `*From*`

`RunAddedToCampaign` / `RunRemovedFromCampaign` carry the preposition because the action targets a sibling aggregate (Campaign), not the Run itself. Bare past-participle (`RunAdded` / `RunRemoved`) would read as if the Run was created or deleted; the preposition makes the cross-aggregate scope explicit. Reserved for events where the Run's stream records an attachment-to-sibling action; sibling Campaign events follow the bare past-participle shape from the Campaign side.

### Projection tables use `proj_<bc>_<aggregate>_<rowtype>`, dropping redundant prefix

Projection tables follow the shape `proj_<bc>_<aggregate>_<rowtype>` where `<rowtype>` names the stored relation (`_summary`, `_membership`, `_children`, `_consumers`, `_ratings`, `_presence`). Examples: `proj_equipment_asset_summary`, `proj_recipe_plan_summary`, `proj_federation_credential_summary`, `proj_trust_visit_summary`.

When the BC contains a single aggregate AND the BC name equals the aggregate name, the redundant prefix is dropped: `proj_<aggregate>_<rowtype>`. Examples: `proj_run_summary`, `proj_agent_summary`, `proj_supply_summary`, `proj_caution_summary`. The dropped-prefix form applies to 8 BCs today (agent, calibration, campaign, caution, decision, run, subject, supply).

When the BC contains a single aggregate but the BC name differs from the aggregate name, the BC prefix stays for grep symmetry with multi-aggregate BCs: `proj_access_actor_summary` (BC = access, aggregate = actor), `proj_data_dataset_summary`, `proj_operation_procedure_summary`, `proj_safety_clearance_summary`.

The `<rowtype>` suffix names the persisted relation, not a usage pattern. Sibling pattern across the corpus: `_summary` (one row per aggregate), `_membership` (join row), `_children` / `_consumers` (reference row), `_ratings` (multi-row per aggregate). The `_lookup` suffix was an early outlier; it was renamed to a relation noun in commit `aaade3cb0`.

### Dataset uses `derived_from` (PROV-O) not `derived_from_ids`

`Dataset.derived_from: frozenset[UUID]` is the sole UUID-collection field that drops the `_ids` suffix the rest of the corpus carries (`Method.needed_family_ids`, `Permit.allowed_credential_ids`, `Asset.family_ids`, etc.). The bare term is the PROV-O standard property (`prov:wasDerivedFrom`); preserving it lets future RO-Crate / PROV-O export round-trip the field without translation.

The `_ids` suffix fitness test (`test_uuid_collection_field_suffix.py`) carves this single field out by name. Adding another PROV-O-aligned field reuses the same carve-out registry entry; do not extend the bare-plural shape outside the PROV-O vocabulary.

### Self-referential parent pointers use `parent_id`

Self-referential parent pointers on aggregate state use the field name `parent_id` with type `<Aggregate>Id | None` (or the bare `UUID | None` carrier where the typed-Id alias has not been introduced). The aggregate's own module namespace already disambiguates the target type, so the verbose `parent_<aggregate>_id` and `part_of_<aggregate>_id` forms are forbidden: `Asset.parent_id`, not `Asset.parent_asset_id`. Cross-aggregate parent pointers keep their qualifier because the qualifier is NOT the aggregate's own name (`Procedure.parent_run_id` references a Run, `Visit.parent_surface_id` references a Surface). The 7 self-parent sites that follow this convention today are `Asset`, `Mount`, `Frame`, `Caution`, `Clearance`, `Visit`, and `Decision`. The rule is enforced by `tests/architecture/test_self_parent_field_naming.py`.

## Documentation

Docstrings carry intent. Comments carry hidden constraints. Test names carry scenarios. Everything else is noise.

No emoji anywhere in source — comments, docstrings, log strings, error messages, `Field(description=...)`. Emoji in source is a documented LLM tell ([LLM Slop Taxonomy](https://github.com/nokusukun/sublime/blob/main/llm-slop-taxonomy.md) Cat 4.5 and 7.1) that accumulates as noise across reviews. Mirrors the no-em-dash rule applied to prose.

### Docstrings

Every public module, class, function, and method gets a docstring. Style is prose, not Sphinx.

- **One imperative summary line.** Single-line docstrings stay on one line: `"""Load and fold a Caution's event stream into current state."""`. End with a period.
- **Prose body when more is needed.** Blank line after the summary, then narrative paragraphs. Use Markdown subheaders (`## Section`) for distinct concerns.
- **Domain vocabulary matches the [glossary](glossary.md).** A slice handler is a handler, not an endpoint. An aggregate is an aggregate, not a model. An evolver is an evolver, not a reducer.
- **Cross-references**:
    - Backticks for in-module symbols: `` `ActorName` ``, `` `evolve()` ``.
    - Dotted path for cross-BC symbols: `` `cora.infrastructure.evolver.require_state` ``.
    - Wiki link only for design memos: `[[project_fold_cost_principles]]`.

**Role-type templates** (established by precedent; copy rather than improvise):

| Role | Module summary | Function summary |
| --- | --- | --- |
| Evolver | "Evolver: replay events to reconstruct `<Aggregate>` state." | `evolve()`: "Apply one event to the current state." / `fold()`: "Replay a stream of events from the empty initial state." |
| Read repo | "Read repository for the `<Aggregate>` aggregate." | `load_<aggregate>()`: "Load and fold a `<Aggregate>`'s event stream into current state." |
| Slice file header | "<role> for the `<slice>` slice." (one each in `route.py`, `tool.py`, `decider.py`, `handler.py`, `command.py`) | n/a |

**Anti-patterns:**

- Do not use `Args:` / `Returns:` / `Raises:` sections. Type annotations are the parameter contract; raised exceptions belong in prose when non-obvious.
- Do not restate the type signature in prose (`"""name (str): The name."""`).
- Do not write `>>>` doctest examples. CORA's tests are external.
- Do not name a phase, iteration, or audit (`Phase 5h`, `Iter B-3`, `DLM-A`, `audit-2026-05-20`) in a docstring. Those rot. The current code is what is true; phase ordering lives in `project_phase_plan.md` and git history. Name the precedent itself (`mirrors get_actor`), not the phase that shipped it.

### Comments

Default to none. Well-named identifiers carry WHAT.

Add a `#` comment only when the WHY is non-obvious: a hidden constraint, a subtle invariant, a workaround for a specific bug, behavior that would surprise a reader. State the constraint, not the history.

**Anti-patterns:**

- Do not narrate WHAT the next line does (`# Set the replaced_by pointer`). The code says that.
- Do not annotate the current task, fix, or caller (`# added for X flow`, `# used by Y`, `# Phase 6i-c membership guard`). Git log and PR description are the right home.
- Do not leave dead-code markers (`# was`, `# previously`, `# old`). Delete the dead code.
- Do not leave `# TODO`, `# FIXME`, `# HACK` without an owner and a trigger. File an issue or drop it.
- Do not use `# noqa: <code>` without a trailing comment explaining the suppression.
- Do not draw section dividers (`# === STATE ===`). The role-typed file layout — one aggregate per file, one slice per directory — already provides navigation. ([antirez](https://antirez.com/news/124) defends "guide comments" as cognitive-load reduction for long single-purpose files; CORA's files don't reach that length.)

### Tests

Test names carry scenarios. Per-test docstrings stay rare.

- **`test_<subject>_<scenario>_<expectation>`** is the naming convention. Long is fine: `test_deactivate_with_none_state_always_raises_not_found`.
- **Property-based tests document the property**, not the test shape. The `@given` body is the test; the docstring is the invariant being verified.
- **Architecture tests document the rule, the rationale, and the exception.** They are the project's structural guardrails; future contributors need to know why each rule exists.
- **Fixture docstrings only when non-obvious.** Per-worker Postgres containers, kernel-construction sites, template-database cloning, and similar subtleties get one paragraph in `conftest.py`. Simple fixtures stay bare.

## Where each family is enforced

| Family | Domain entry point | Shared infrastructure |
| --- | --- | --- |
| Identifiers | `IdGenerator` port; per-aggregate `external_id` field | `cora.shared.identity`, `cora.shared.identifier`, `cora.infrastructure.ports.id_generator` |
| Units of measurement | declarer's JSON Schema; allowlist of `system` namespaces | `cora.shared.json_schema_validation` |
| Personal data | `Actor` state; `profile` table | `cora.access.aggregates.actor.profile` |
| Schema-validated values | declarer's schema field; carrier's values field | `cora.shared.json_schema_validation`, `cora.shared.json_schema_subset` |
| Documentation | docstring on every public symbol; sparse `#` comments | [Glossary](glossary.md) for vocabulary |

For the deeper rules each family inherits from (event sourcing, value-object scope, field grouping), see [Modeling](modeling.md). For the read-side, idempotency, and cross-aggregate validation patterns, see [Patterns](patterns.md).
