# Model

*The developer's index into where I11 content lives. Design-phase.*

I11 is a documentation-and-descriptor scaffold: it exists as the descriptor and docs below, not yet as registered events or integration scenarios.

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/i11/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i11/beamline.yaml) | the device walk, with the dodal-derived EPICS PV handles; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/diamond/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/diamond/site.yaml) | the Diamond facility surface; I11 added to its beamlines, with a powder-diffraction practice carried pending |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | **no change in this scaffold.** I11 reuses existing Families and the loose `StorageRing` / `TemperatureController`. The earned `TemperatureController` graduation is routed to a separate gate-reviewed change (see below) |
| Catalog Role | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) + `cora.equipment.aggregates.role.SEED_ROLES` | **no change in this scaffold.** The earned settable-continuous-setpoint actuator Role is a code change to `SEED_ROLES` (drift-guarded), routed to gate-review |
| Catalog Capability / Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the powder-diffraction Capability is deferred until the technique enters scope (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape |
| Trust / governance | not yet instantiated | see [Governance](governance.md), including the robot Clearance |

## The earn, and why it is not in this PR

I11 is the deployment that genuinely earns an abstraction CORA has deferred since 7-BM: a **settable-continuous-setpoint actuator**. Its four thermal actuators (two Cyberstar/Eurotherm blowers, two Oxford cryostreams) are `Locatable[float]` with `set(value)`/`setpoint`/`ramprate`/PID. After the loose `TemperatureController` family was carried at I22 and I03, I11 is the rule-of-three.

That earns two things:

1. **Graduating the `TemperatureController` Family** (catalog `families:` add, like I03's Goniometer).
2. **A new settable-continuous-setpoint actuator Role** (CORA has none: Positioner is spatial, Controller supervises, GenericProbe is read-only).

The Role is a **code change** to `cora.equipment.aggregates.role.SEED_ROLES`, which is drift-guarded by an exact-match test (`test_roles_match_seed_roles`), and is core cross-facility vocabulary. Per the gate-review discipline, that does not belong in a families-only scaffold PR; it is routed to a **separate, gate-reviewed change** (TEMP-1). Graduating the Family is coupled to the Role (a `TemperatureController` Family presenting a non-existent Role would be hollow), so both land together in that change. This scaffold carries the actuators loose, as I22 and I03 did, and records the trigger.

## What is deliberately not here yet

- **The TemperatureController graduation + settable-actuator Role** (gate-reviewed follow-up, TEMP-1).
- **New Capabilities / Methods and vendor Models.** The powder-diffraction Method is carried pending; no Model is bound.
- **The robot as a Family.** It presents the existing Positioner Role; shape deferred (ROBOT-1).
- **Integration scenarios.** No `test_i11_*.py` registers I11 Assets.
- **Operations and experiment views.** See the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
