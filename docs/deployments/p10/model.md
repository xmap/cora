# Model

*The developer's by-kind index: where each CORA aggregate's P10 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P10 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (coupled axes) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes P10 new

P10 is a sixth beamline at an existing Site, and a further XPCS beamline after the APS 8-ID and NSLS-II CHX exercises. Its science is coherent hard X-ray applications: XPCS, coherent diffraction imaging / ptychography, and coherent-beam diffraction, across three experiment areas. Its modelling first is the practice binding: P10's XPCS practice binds the **graduated** catalog `xpcs` Method directly, the first PETRA III practice whose Method is already earned (the others all carry pending practices). This is the reuse-earns-the-abstraction principle in action: a technique graduated at one facility (8-ID, EPICS) carries cleanly to another (PETRA III, Tango) without re-coining.

## No new families

P10 coins no new Family. The undulator binds `InsertionDevice`; the mono `Monochromator`; the CRL `Transfocator`; the hexapod `Hexapod`; the slits `Slit`; the mirrors `Mirror`; the two-theta arm `RotaryStage`; the sample / optics / nano stages `LinearStage`; the coupled axes `PseudoAxis`; the beam shutter `Shutter`; the wide detector suite `Camera`; the fluorescence detectors `EnergyDispersiveSpectrometer`; the LAB simulated diffractometer `Goniometer`. Nothing in the catalog changes. The Mythen strip detector is modelled as a `Camera` for now (a fold-vs-promote question deferred to the catalog owner, `DET-1`).

## The control plane

P10 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, with the widest controller and detector diversity in the set (OMS, Galil DMC, SmarAct, AttoCube, hexapod, spk; Pilatus / Eiger / Lambda / PCO / Andor / Mythen / Quadro / Lima). The handles are read from P10's public OnlineXML registry and carried confirm (`CTRL-1`); the Lambda and Lima cameras report on a bare `p10` host (`HOST-1`). The XPCS acquisition (the coherent beam read by the high-frame-rate detector, the correlation computed downstream) runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, and the correlation compute is `ComputePort` work, the same shape as the 8-ID XPCS seam.

## Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The OnlineXML exposes the gap, not the period; carried pending.
- **The optics detail (`OPT-1`).** The DCM crystal cut, the optics-bank breakdown, the CRL focal sizes, and the mirror coatings are carried confirm-pending.
- **The motor-bank axis roles (`GROUP-1`).** The `OPT_MOT`, `E1_MOT`, `E2_MOT` banks carry no per-axis role; grouped as stage Assets.
- **The E2 / LCX sample detail (`SAMPLE-1`, `LCX-1`).** The sample-piezo / two-theta geometry and the LCX sub-station role are pending.
- **The LAB status (`LAB-1`).** The LAB devices are simulation / test units; whether they are modelled as a live offline endstation or excluded is pending.
- **The detector roster (`DET-1`).** The XPCS-detector assignment (Lambda vs Eiger), the detector models, and the Mythen fold-vs-promote are named, not fully bound.
- **The host mapping (`HOST-1`).** The Lambda / Lima cameras report on a bare host; whether shared Tango DB or registry artifact is pending.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **`ptychography` Method (`TECH-1`).** Whether coherent imaging enters CORA's catalog is an owner decision; the practice renders unlinked, pending. (XPCS already binds the graduated Method.)
- **The PSS permit signals (`PSS-1`).** The beam shutter is read but the permit leaves are not; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p10_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
