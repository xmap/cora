# Model

*The developer's index into where P04 content lives, its place as CORA's first soft X-ray / grating-monochromator deployment, and the record of what is deliberately deferred. First cut.*

P04 is a descriptor-and-docs scaffold today, reverse-engineered from P04's public OnlineXML registry: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/p04/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p04/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; Tango handles read from the OnlineXML (`CTRL-1`) |
| Site descriptor | [`deployments/petra-iii/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/petra-iii/site.yaml) | the existing PETRA III facility surface (shared with P01); P04 adds the soft X-ray Practices |
| Upstream source | [P04 OnlineXML](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p04) | the beamline's own public OnlineXML Tango device registry the descriptor was reverse-engineered from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed; P04 is the first `GratingMonochromator` deployment but it is already a Family |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; soft X-ray spectroscopy reuses the pending `xas_spectroscopy` / `angle_resolved_photoemission` slugs (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers P04 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes P04 new

P04 is a second beamline at an existing Site, and the fleet's entry into the soft X-ray regime. It is **CORA's first `GratingMonochromator` deployment**: its monochromator is a plane-grating monochromator (the soft X-ray analog of the crystal `Monochromator`), not the Bragg crystal mono the hard X-ray beamlines use. Its science is soft X-ray spectroscopy at 250-3000 eV (XAS via total electron yield, and photoemission), fed by a variable-polarization APPLE-II-type undulator.

## No new families (the one new binding is already in the catalog)

P04 coins no new Family. The plane-grating monochromator binds the catalog `GratingMonochromator` (its first deployment, but the Family exists); the undulator binds `InsertionDevice`; the mirrors bind `Mirror`; the slits bind `Slit`; the sample manipulators bind `Manipulator`; the diagnostic cameras bind `Camera`; the electrometers bind `FluxMonitor`; the virtual axes bind `PseudoAxis`; and the motorized phosphor screens bind the loose `Screen` (held across the fleet, the 2-BM `FLAG-1` precedent). Nothing in the catalog changes.

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

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
