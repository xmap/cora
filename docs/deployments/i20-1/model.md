# Model

*The developer's by-kind index: where each CORA aggregate's I20-1 content lives. It hosts no content of its own. Design-phase scaffold, deliberately partial.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at I20-1 |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory](inventory.md#the-asset-tree) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](equipment/index.md) (I20-1-OH optics, I20-1-EH experiment) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), and a deliberately partial one: the dodal commissioning module is thin. Left out on purpose:

- **The dispersive heart of EDE.** The bent-crystal polychromator (POLY-1) and the position-sensitive strip detector (STRIP-1), the two devices that make the technique energy-dispersive, are not in the public source, so they are named open questions, not modelled. The polychromator would be a genuinely new optic class (an energy-fanning bent crystal, distinct from `Monochromator` / `GratingMonochromator`); CORA would weigh a `Polychromator` Family once it is PV-bound, not before. Coining it from no source PV would be invention.
- **No new Family, no loose family.** What is modelled reuses existing families only: the turbo slit binds `Slit`, the PMAC `MotionController`, the PandA `TimingController`, the sample stage the graduated `Manipulator`, the Xspress3 the graduated `EnergyDispersiveSpectrometer`.
- **The mock / skip honesty.** The sample stage is a dodal `mock` (real PVs, motors being reconnected, STAGE-1); the Xspress3 is a dodal `skip` (defined, not loaded by default, DET-1). Both are carried `confirm` and flagged, not asserted live.
- **The absent source / optics / diagnostics chain.** No source, front-end, primary mirror, attenuator, ion chamber, flux monitor, or beam-position monitor is in the commissioning module; the source is carried PV-less (SRC-1) and the rest are open questions.
- **No new Capability or Method.** Energy-dispersive EXAFS is a pending Practice on the Site (the dispersive complement to the BMM energy-scan question, TECH-1); MX3-style, the technique is reinforced-and-deferred, not coined.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive, and whose primary detector is not even in source, would be invention; they land when the dispersive devices are PV-bound and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
