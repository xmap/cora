# Capabilities

*Recipe BC Capabilities. A Capability is the operations-layer template that declares WHAT an operation provides: the [Affordances](../reference/affordances.md) any wired Asset's Families must cover (`required_affordances`), the parameter contract any binding Method must be a structural subset of (`parameters_schema`), and which executor kinds may bind (`executor_shapes` — closed v1 enum `{METHOD, PROCEDURE}`). Methods bind to one Capability via `capability_id`; at `define_plan` time, every wired Asset's Families' affordances must cover the bound Method's Capability's `required_affordances` (otherwise `PlanAffordancesNotSatisfiedError`, 409). Capabilities are cross-facility vocabulary: codes are namespaced `cora.capability.*` (closed core) with `cora.capability.<facility>.*` available for site-specific extensions. See [Model](../architecture/model.md) for the aggregate shape.*

## Closed core (v1)

| Code | Name | Binds Methods | Notes |
| --- | --- | --- | --- |
| `cora.capability.tomography` | Tomography | `tomography`, `streaming_tomography`, `continuous_rotation_tomography`, `mosaic_tomography` | The canonical synchrotron-CT science technique. Direct analogue to NeXus `NXtomo` / PaNET `tomography`. Executor shape: `METHOD`. |
| `cora.capability.acquisition` | Acquisition | `first_light`, `dark_baseline`, `flat_baseline` | The operational primitive for frame-stack capture. Distinct from `tomography` — `acquisition` is the bare "produce frames" primitive (NeXus `NXscan` analogue); `tomography` is the specific rotational-projection technique on top. |
| `cora.capability.alignment` | Alignment | `resolution_alignment`, `focus_alignment`, `center_alignment`, `roll_alignment`, `pitch_alignment` | Iterative tuning toward a target metric. Each Method is a distinct step in the rotation-axis alignment chain; the Capability is the shared operational primitive (iterate-observe-adjust). |
| `cora.capability.calibration` | Calibration | `alignment_calibration` | Empirical measurement of system constants (motor sensitivities, beam profiles, encoder offsets). Distinct from `alignment` — calibration *measures* constants, alignment *consumes* them. |
| `cora.capability.maintenance` | Maintenance | `motor_homing`, `hexapod_reboot` | One-shot setup, recovery, and ceremony operations with no scientific Dataset output. Currently exercised via both `METHOD` (recipe-ladder anchoring) and `PROCEDURE` (ISA-106 step-by-step ceremony executor) shapes. |

## Naming conventions

- **`cora.capability.<snake_case>`** — lowercase, regex `^[a-zA-Z0-9_-]{1,64}$` (matches MCP / OpenAI / Anthropic tool-name constraints so the unprefixed tail can be exposed verbatim on agent tool surfaces).
- **Noun or gerund only, never verb.** Verbs belong at the [Affordance](../reference/affordances.md) (`-able` adjective) or agent-tool layer (`get_*`, `read_*`). Capability names describe *what an operation provides*.
- **One word when a community shorthand exists** (`tomography`, `alignment`, `acquisition`); head-noun-last `snake_case` compound only when one word is genuinely ambiguous (for example, future `energy_scan` vs ambiguous bare `energy`).
- **Artifacts and milestones are NOT Capabilities.** `baseline` is a Dataset kind; `first_light` is a milestone (the Method captures the operational acquisition, the milestone-name stays only because the synchrotron community universally calls it that). Data-reduction steps (for example, `flat_field_correction`) live in external pipelines, not as CORA Methods.

## Catalog governance

- **Closed core under `cora.capability.*`**, with `cora.capability.<facility>.*` available for site-specific extensions on demand (FHIR/LOINC `status` + `replaced_by` precedent).
- **Status FSM** `Defined → Versioned → Deprecated`; deprecated codes carry optional `replaced_by_capability_id` for cross-version lineage.
- **`executor_shapes` is REQUIRED non-empty** at definition. Closed v1 set: `{METHOD, PROCEDURE}`. A Capability may declare both.
- **Adding a value** is additive only — deprecate-and-replace, never remove. Replay safety.

## Pending in code

- `cora.capability.energy_scan` — Method-binding for `energy_change` style scans (currently `energy_change` binds to `tomography`).
- `cora.capability.steering` — Method-binding for mid-flight `adjust_run` steering flows.

## Related

- [Methods](methods.md) — the Method catalog, with each Method's Capability binding in the second column.
- [Affordances](../reference/affordances.md) — the closed 29-item primitive set Capabilities declare as `required_affordances`.
- [Glossary](../reference/glossary.md) — Capability vs Family vs Affordance vs Method distinctions.
