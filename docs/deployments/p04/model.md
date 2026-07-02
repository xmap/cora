# Model

*The developer's by-kind index: where each CORA aggregate's P04 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P04 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (incident-energy axis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes P04 new

P04 is a second beamline at an existing Site, and PETRA III's entry into the soft X-ray regime (the fleet's soft X-ray line was opened by NSLS-II SIX). It **binds the catalog `GratingMonochromator` Family** (introduced at SIX, graduated at CSX): its monochromator is a plane-grating monochromator (the soft X-ray analog of the crystal `Monochromator`), not the Bragg crystal mono the hard X-ray beamlines use. Its science is soft X-ray spectroscopy at 250-3000 eV (XAS via total electron yield, and photoemission), fed by a variable-polarization APPLE-II-type undulator.

## No new families (the one new binding is already in the catalog)

P04 coins no new Family. The plane-grating monochromator binds the catalog `GratingMonochromator` (its first deployment, but the Family exists); the undulator binds `InsertionDevice`; the mirrors bind `Mirror`; the slits bind `Slit`; the sample manipulators bind `Manipulator`; the diagnostic cameras bind `Camera`; the electrometers bind `FluxMonitor`; the virtual axes bind `PseudoAxis`; and the motorized phosphor screens bind the catalog `Screen` Family (the 2-BM `FLAG-1` precedent). Nothing in the catalog changes.

## The control plane

P04 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as P01. The soft X-ray specifics are the device classes (the `MonoP04` plane-grating monochromator, the `UndulatorP04` variable-polarization undulator, the SmarPod-style `spk` mirror controllers, the `Keithley6517A` electrometers, the `TangoVimba` diagnostic cameras). The handles are read from P04's public OnlineXML registry and carried confirm (`CTRL-1`); some optics report on the `haspp04exp2` host but are the optics section (`HOST-1`). The soft X-ray absorption acquisition (the undulator + PGM photon-energy scan read against the electrometer) runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

## Deliberately not here yet

- **The undulator polarization control (`SRC-1`).** The OnlineXML exposes the gap, not the APPLE-II row-phase / polarization axes; carried pending.
- **The optics physical detail (`OPT-1`).** The grating line densities, the included-angle / c-value mode, the mirror coatings, and the exit-slit calibration are carried confirm-pending.
- **The manipulator axis roles (`GROUP-1`).** The `exp1_mot01..16` and `ps2.01..14` banks carry no per-axis role in the registry; grouped as `Manipulator` Assets, roles pending.
- **The EXSU2 sub-roles (`EXSU-1`).** The exit-shutter unit's slit / bpm / baffle breakdown is pending.
- **The detection channels (`DET-1`).** The electrometer measured channels and the photoemission analyzer (not a motor row) are named, not bound.
- **The host mapping (`HOST-1`).** The optics report on the experiment host; whether this is a shared Tango DB or a registry artifact is pending.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The soft X-ray Methods (`TECH-1`).** Whether XAS and photoemission enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the existing slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p04_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
