# Model

*The developer's by-kind index: where each CORA aggregate's P61 content lives, its place as the last OnlineXML-modelled PETRA III beamline, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P61 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes P61 new

P61 is a seventeenth beamline at an existing Site, the facility's high-energy white-beam wiggler beamline (P61A Large Volume Press + P61B energy-dispersive diffraction). It is the **last PETRA III beamline with a public OnlineXML registry**, completing CORA's OnlineXML-driven coverage of the facility. At the modelling level it is a reuse-and-reinforce deployment, and a deliberately thin one given its sparse registry slice (one generic motor bank).

## No new families (a thin, honest model)

P61 coins no new Family. The motor bank binds `LinearStage`; the energy-dispersive detector is a pending `EnergyDispersiveSpectrometer` placeholder. Nothing in the catalog changes. The Large Volume Press (P61A), when exposed, would reuse the catalog `PressureCell` Family (graduated across 13-id and P02); it is carried pending (`PRESS-1`). The P61 registry slice exposes little beyond the grouped motor bank, so the source, the press, and the detectors are carried pending rather than invented, the model-what-the-source-supports posture as P11 / P21 / P23.

## The control plane

P61 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, with one quirk: P61 is the only PETRA III extras package on the `debian/stretch` branch (the others are `debian/jessie`), so its snapshot vintage may differ. The handles are read from P61's public OnlineXML registry and carried confirm (`CTRL-1`). The energy-dispersive diffraction acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

## Deliberately not here yet

- **The source (`SRC-1`).** P61 is a damping-wiggler beamline (`source: superconducting-wiggler`); the wiggler parameters are not exposed in this registry slice.
- **The Large Volume Press (`PRESS-1`).** P61A's press is not in the registry slice; would reuse the catalog `PressureCell` Family when exposed.
- **The motor-bank axis roles (`GROUP-1`).** The `eh_mot*` bank carries no per-axis role; grouped as one stage.
- **The detectors (`DET-1`).** The Ge energy-dispersive detector and any area detector are not in the registry slice; carried as a pending placeholder.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/stretch` (unusual for the set); some handles may lag the live Tango database.
- **The diffraction Method (`TECH-1`).** Whether it enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p61_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
