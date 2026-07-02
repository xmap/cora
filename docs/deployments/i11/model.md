# Model

*The developer's by-kind index: where each CORA aggregate's I11 content lives, the settable-continuous-setpoint actuator Role it earns, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at I11 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## The earn, and why it is not in this PR

I11 is the deployment that genuinely earns an abstraction CORA has deferred since 7-BM: a **settable-continuous-setpoint actuator**. Its four thermal actuators (two Cyberstar/Eurotherm blowers, two Oxford cryostreams) are `Locatable[float]` with `set(value)`/`setpoint`/`ramprate`/PID. After the loose `TemperatureController` family was carried at I22 and I03, I11 is the rule-of-three.

That earns two things:

1. **Graduating the `TemperatureController` Family** (catalog `families:` add, like I03's Goniometer).
2. **A new settable-continuous-setpoint actuator Role** (CORA had none at the time: Positioner is spatial, Controller supervises, GenericProbe is read-only).

The Role was a **code change** to `cora.equipment.aggregates.role.SEED_ROLES`, which is drift-guarded by an exact-match test (`test_roles_match_seed_roles`), and is core cross-facility vocabulary. Per the gate-review discipline, that did not belong in a families-only scaffold PR; it was routed to a **separate, gate-reviewed change** (TEMP-1). Graduating the Family is coupled to the Role (a `TemperatureController` Family presenting a non-existent Role would be hollow), so both landed together in that change: `TemperatureController` is now a catalog Family presenting the new `Regulator` Role. This scaffold carried the actuators loose, as I22 and I03 did, and recorded the trigger.

## What is deliberately not here yet

- **The TemperatureController graduation + `Regulator` Role**: not part of this families-only scaffold; landed via the gate-reviewed follow-up (TEMP-1).
- **New Capabilities / Methods and vendor Models.** The powder-diffraction Method is carried pending; no Model is bound.
- **The robot as a Family.** It presents the existing Positioner Role; shape deferred (ROBOT-1).
- **Integration scenarios.** No `test_i11_*.py` registers I11 Assets.
- **Operations and experiment views.** See the [index](index.md#not-yet-documented).
