# Model

*The developer's index into where P09 content lives, its place as the second consumer of the 4-ID polarization / magnetism vocabulary, and the record of what is deliberately deferred. First cut.*

P09 is a descriptor-and-docs scaffold today, reverse-engineered from P09's public OnlineXML registry: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/p09/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p09/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page; Tango handles read from the OnlineXML (`CTRL-1`) |
| Site descriptor | [`deployments/petra-iii/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/petra-iii/site.yaml) | the existing PETRA III facility surface (shared with P01, P04, P06, P11, P03, P10); P09 adds the resonant / magnetic Practices |
| Upstream source | [P09 OnlineXML](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p09) | the beamline's own public OnlineXML Tango device registry the descriptor was reverse-engineered from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none changed here; P09 reuses the catalog `PhaseRetarder` and `PolarizationAnalyzer` Families plus the allowlisted-loose `Magnet` Family and the other catalog Families |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; resonant / magnetic scattering + XMCD reuse the pending `resonant_scattering` / `magnetic_scattering` / `xmcd` slugs (`TECH-1`) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers P09 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What makes P09 new

P09 is a seventh beamline at an existing Site, and the richest of the PETRA III set in technique breadth: resonant elastic X-ray scattering and HAXPES (MONO), diffraction (DIF), and high-field magnetism / XMCD (MAG, a 14 T magnet). At the modelling level it is the **second consumer of the polarization / magnetism vocabulary** the APS 4-ID deployment introduced: the phase retarder, the polarization analyzer, and the high-field magnet.

## No new families (the 4-ID vocabulary ports cleanly)

P09 coins no new Family. It binds the catalog `PhaseRetarder` Family (P09 was the second consumer, the rule-of-three signal with P22 that earned it into the catalog) and the graduated catalog `PolarizationAnalyzer` Family (earned across 4-ID / i10 / ID32 / P09, presenting Positioner) for its analyzer, and reuses one allowlisted-loose Family from 4-ID (`Magnet`), becoming a further consumer, the rule-of-three signal toward its eventual graduation (a catalog-owner decision, not coined here). The diffractometers bind the catalog `Goniometer` Family (not the composed `Diffractometer` Assembly, the same call as P01 EH2); the optics bind `Monochromator` / `Mirror` / `Transfocator` / `Slit` / `Filter`; the sample environment binds `TemperatureController` / `Hexapod` / `LinearStage`; the detectors bind `Camera` / `EnergyDispersiveSpectrometer`. P09 itself changes nothing in the catalog.

## The control plane

P09 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines. Its instrument diversity is high (OMS / VME58 steppers, Galil slits, PI + AttoCube piezos, a hexapod; PerkinElmer / Pilatus / Andor detectors, the SIS3302 digitizer, GPIB instruments). The handles are read from P09's public OnlineXML registry and carried confirm (`CTRL-1`). The resonant-scattering / magnetism acquisition (the energy / diffractometer / field scan with polarization switching) runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, the same shape as the 4-ID seam.

## Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The OnlineXML exposes the gap, not the period; carried pending.
- **The optics detail (`OPT-1`).** The DCM crystal cut, the mirror coatings, and the CRL detail are carried confirm-pending.
- **The diffractometer structure (`DIFF-1`).** The MONO / DIF / MAG six-circle counts and detector arms are pending; modelled as `Goniometer` Assets, not `Diffractometer` Assemblies.
- **The motor-bank axis roles (`GROUP-1`).** The MONO / DIF `p09/motor` banks carry no per-axis role; grouped as stage Assets.
- **The polarization / magnet detail (`POL-1`, `MAG-1`).** The phase-retarder / analyzer geometry and the 14 T magnet field / control are pending; the Families are the allowlisted-loose 4-ID ones.
- **The detector roster (`DET-1`).** The detector models and the SIS3302 channel count (collapsed from the registry's ROI explosion) are named, not fully bound.
- **The host mapping (`HOST-1`).** A shared Lambda reports on the bare `petra3` host; a stray `p07/hexapodsmall` row (a P07 device) is excluded from P09.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The resonant / magnetic Methods (`TECH-1`).** Whether they enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the existing slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p09_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
