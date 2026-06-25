# Model

*The developer's index into where I15-1 content lives. Design-phase.*

I15-1 is a documentation-and-descriptor scaffold: it exists as the descriptor and docs below, not yet as registered events or integration scenarios.

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/i15-1/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i15-1/beamline.yaml) | the device walk, with the dodal-derived EPICS PV handles; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/diamond/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/diamond/site.yaml) | the Diamond facility surface; I15-1 added to its beamlines, with a total-scattering practice carried pending |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | **no new family coined by I15-1.** It reuses existing Families and the loose `StorageRing` (from I22); its incident-flux monitor reuses `FluxMonitor`, since graduated to a catalog Family (presenting the Sensor Role) on the i22/i03/i15-1 rule-of-three |
| Catalog Capability / Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the total-scattering Capability is deferred until the technique enters scope (TECH-1) |
| Catalog Model | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none bound |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape |
| Trust / governance | not yet instantiated | see [Governance](governance.md), including the interlock-as-permit and the robot Clearance |

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

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
