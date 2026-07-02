# Model

*The developer's by-kind index: where each CORA aggregate's P08 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P08 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes P08 new

P08 is a twelfth beamline at an existing Site, the facility's high-resolution diffraction beamline (surface / interface diffraction, reflectivity, high-resolution powder / single-crystal). At the modelling level it is a reuse-and-reinforce deployment: nothing new at the vocabulary level, distinguished mainly by its rich detector set.

## No new families

P08 coins no new Family. The DCM and multilayer mono bind `Monochromator`; the CRL `Transfocator`; the absorber `Filter`; the six-circle Kohzu diffractometer `Goniometer`; the hexapod `Hexapod`; the slits `Slit`; the detectors `Camera` / `EnergyDispersiveSpectrometer`. Nothing in the catalog changes. The Mythen2 strip detector is modelled as a `Camera` for now (a fold-vs-promote question for the catalog owner, the P10 precedent).

## The control plane

P08 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines. Its distinctive devices are the Kohzu six-circle diffractometer controller and the breadth of detectors (Eiger / Pilatus / Mythen / PerkinElmer / Vortex). The handles are read from P08's public OnlineXML registry and carried confirm (`CTRL-1`). The high-resolution diffraction acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

## Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The gap is read; the period is not exposed.
- **The optics detail (`OPT-1`).** The DCM / multilayer crystal cut and the CRL detail are carried confirm-pending.
- **The diffractometer structure (`DIFF-1`, `GROUP-1`).** The six-circle Kohzu geometry and the per-axis `diff*` bank roles are pending; modelled as a `Goniometer` Asset.
- **The sample hexapod geometry (`SAMPLE-1`).** Carried confirm-pending.
- **The detector roster (`DET-1`).** The models, the operative roster, and the Mythen fold-vs-promote are named, not fully bound.
- **The shared Lambda host (`HOST-1`).** A Lambda reports on the bare `petra3` host.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The diffraction Method (`TECH-1`).** Whether it enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p08_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
