# Model

*The developer's by-kind index: where each CORA aggregate's I15-1 content lives, why it adds no catalog kinds and reinforces the existing model, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at I15-1 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Why I15-1 adds no catalog kinds

I15-1 was picked partly expecting it to graduate the open settable-actuator affordance from its `SafeOrBeamPositioner` sample-environment devices. A source-level adversarial eval **refuted that**, and the refutation is the modelling content of this deployment:

- **`SafeOrBeamPositioner` folds into Positioner.** It is a `Movable` that drives a motor to two named positions (SAFE / BEAM), which is the existing Positioner Role with Indexable named positions, not a new affordance. It is also **not** a `TemperatureController`: the dodal classes are named for temperature controllers (blower / cobra / cryostream) but model only the in/out-of-beam move, so calling them `TemperatureController` would mirror the class name rather than the behaviour (intentional-modelling-not-mirroring). Modelled as `LinearStage` + Positioner / Indexable (SAFEBEAM-1).
- **The `rail` folds into Table** (the TomoWISE DetectorGantry precedent), not a new `Rail` Family (RAIL-1).
- **The interlocks fold into the Enclosure permit**, not an equipment Family (INTERLOCK-1).

So I15-1 is a reuse + reinforce deployment: it provides the third `FluxMonitor` deployment that completed its rule-of-three graduation into the catalog, and adds a third robot-as-Positioner instance, while coining no new vocabulary of its own. That is a result, not a gap: the value is confirming the existing model absorbs a new technique cleanly.

## What is deliberately not here yet

- **New Capabilities / Methods and vendor Models.** The total-scattering Method is carried pending; no Model is bound.
- **The robot as a Family.** It presents the existing Positioner Role; shape deferred (ROBOT-1).
- **Integration scenarios.** No `test_i15_1_*.py` registers I15-1 Assets.
- **Operations and experiment views.** A runbook for an unmodelled beamline would be invention; see the [index](index.md#not-yet-documented).
