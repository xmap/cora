# Catalog

*Cross-facility vocabulary: the kinds shared across APS, MAX IV, and any future site CORA serves. This page explains how the catalog works; the inventories themselves are generated from the [`catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) descriptor.*

## How the vocabulary composes

The kinds below are not five separate lists; they are one chain, sliced per kind for lookup. A measurement technique enters CORA as a [Method](methods.md). A Method declares the device [Families](families.md) it needs and the [Capability](capabilities.md) contract it realizes. A Family advertises which functional [Roles](roles.md) it can satisfy (`presents_as`), and a Role in turn requires a closed set of [Affordances](../reference/affordances.md), the primitive verbs a device supports. When a beamline is built, an Asset binds a vendor [Model](models.md) to record the specific hardware that fills a Family. So the chain reads: a Method needs Families, Families present Roles, Roles require Affordances, and Models are the concrete hardware that satisfy Families. The per-kind pages below are that one chain, each viewed from one link.

## Inventories

- [Capabilities](capabilities.md): Recipe BC operations-layer templates (`cora.capability.*`), the namespace for what an operation provides. Each Method binds one Capability.
- [Methods](methods.md): Recipe BC technique catalog (ISA-88 General Recipe layer). Each Method declares the device Families it needs and the Capability contract it realizes.
- [Families](families.md): Equipment BC device-class abstractions, the contract a Method declares as `needed_families`.
- [Roles](roles.md): Equipment BC functional binding contracts. Methods reference these via `required_roles`; Families and Assemblies advertise satisfaction via `presents_as`.
- [Models](models.md): the vendor product catalog. A beamline Asset binds a Model to record what specific hardware it is.

## Naming conventions

- **`cora.capability.<snake_case>`** for Capability codes: validated as trimmed, non-empty, must start with the `cora.capability.` prefix, carry a non-empty suffix after it, and stay within 200 characters. There is no enforced character-class regex today; keeping the unprefixed tail short and `snake_case` is a convention so it can be exposed verbatim on agent tool surfaces, matching MCP / OpenAI / Anthropic tool-name constraints.
- **Noun or gerund, never verb.** Verbs belong at the [Affordance](../reference/affordances.md) (`-able` adjective) or agent-tool (`get_*`, `read_*`) layer. A Capability name describes what an operation provides.
- **One word when a community shorthand exists** (`tomography`, `alignment`, `acquisition`); a head-noun-last `snake_case` compound only when one word is genuinely ambiguous (a future `energy_scan` versus a bare `energy`).
- **Artifacts and milestones are not Capabilities.** `baseline` is a Dataset kind; `first_light` is a milestone the community names. Data-reduction steps live in external pipelines, not as CORA Methods.

## Governance

- **Closed core** under `cora.capability.*`, with `cora.capability.<facility>.*` available for site-specific extensions on demand.
- **Status FSM** `Defined -> Versioned -> Deprecated`; a deprecated code carries an optional `replaced_by` pointer for cross-version lineage.
- **`executor_shapes` is required and non-empty** at definition (closed set `{Method, Procedure}`; a Capability may declare both).
- **Additive only.** Deprecate-and-replace, never remove, for replay safety.

## Roles

The four Roles (`Imager`, `Positioner`, `Controller`, `Detector`) ship as a closed-core seed registry. A fifth candidate, `Conditioner` (attenuators / shutters / mirrors), was deferred: no affordance is universally required across those Families, so the required-set would be vacuous. A rule-of-three trigger gates a future definition.

Every `RoleId` is `uuid5(_ROLE_NAMESPACE, name.lower())` with `_ROLE_NAMESPACE = uuid5(NAMESPACE_DNS, 'cora.role')`. Deterministic ids make a Method authored at APS 2-BM bind against the same Role uuid when shipped to MAX IV or DLS. A `define_role` with a seed Role's name collides on the same stream and returns 409.

## Families: settings over subtypes

Some apparent new families are settings axes, not family axes. A high-framerate camera lands as a `Camera` Asset with extended settings (`max_framerate_hz`, `sensor_kind`, `readout_mode`), not a `HighSpeedCamera` family, mirroring the `Mirror` precedent (multilayer is a settings field, not a subtype). `TimingController` is the defined Family for trigger / gate / sync-pulse hardware (the second `<Domain>Controller` family after `MotionController`, anchored at 2-BM by the softGlueZynq FPGA); `OpticalRelay` is the future composing-family name for scintillator-objective-camera relays once the MCTOptics composition splits its composing family from its `Imager` presenter.

## Source of truth

Roles and the closed affordance / executor-shape vocabularies are code-defined and validated against the code by drift-guard tests. Families, Capabilities, Methods, and Models are authored in `catalog.yaml`, which supersedes the scenario fixtures as the consolidated source. Until the seeder inversion lands, the code seeds remain authoritative for what CORA actually registers; `catalog.yaml` is the docs projection, kept honest by the round-trip and roles drift-guard tests.
