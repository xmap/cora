# Model

*The developer's by-kind index: where each CORA aggregate's P07 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P07 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes P07 new

P07 is an eleventh beamline at an existing Site, and the facility's high-energy materials-science beamline, jointly operated by Helmholtz-Zentrum Hereon (2/3) and DESY (1/3). Its distinguishing capabilities are high-energy diffraction for engineering materials and a 17 T high-field magnet endstation. At the modelling level it is a reuse-and-reinforce deployment, plus a governance note (the joint operation).

## No new families

P07 coins no new Family. The multi-bounce mono binds `Monochromator`; the four-circle diffractometer `Goniometer`; the hexapod `Hexapod`; the 17 T magnet the graduated catalog `Magnet` Family (a further consumer, after 4-ID / i10-1 / ID32 / P09); the Linkam stage `TemperatureController`; the slits `Slit`; the stages `LinearStage`; the detectors `Camera` / `EnergyDispersiveSpectrometer`. Nothing in the catalog changes.

## The control plane

P07 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, despite the Hereon / DESY joint operation (the beamline controls are the PETRA III stack). Its distinctive devices are the multi-bounce DCM (resolved axes), the 17 T magnet, and the Linkam stage. The handles are read from P07's public OnlineXML registry and carried confirm (`CTRL-1`); only the EH2 registry slice is public. The high-energy diffraction / high-field acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

## Deliberately not here yet

- **The joint-operation governance (`OPERATOR-1`).** The Hereon (2/3) + DESY (1/3) operation is a facility-governance fact carried as a question; how it maps to CORA's Federation / Trust model is pending.
- **The undulator parameters (`SRC-1`).** The gap / taper are read; the period is not exposed.
- **The optics detail (`OPT-1`).** The multi-bounce DCM crystal cut and the OH optics are carried confirm-pending.
- **The diffractometer structure (`DIFF-1`).** The four-circle count and the detector arm are pending; modelled as a `Goniometer` Asset.
- **The motor-bank axis roles (`GROUP-1`).** The `exp*` / `oh*` banks carry no per-axis role; grouped as stage Assets.
- **The magnet detail (`MAG-1`).** The 17 T field and control are pending; the Family is the graduated catalog `Magnet` (a further consumer, its per-Asset field detail pending).
- **The detector roster (`DET-1`).** The models and the EH2B detection are named, not fully bound.
- **The other hutches (`HOST-1`).** Only the EH2 slice is public; EH1 / EH3 / EH4 are noted, not modelled.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The diffraction Methods (`TECH-1`).** Whether they enter CORA's catalog is an owner decision; the Practices render unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p07_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
