# Notes

## Techniques

*What the modelled part of P09 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P09's resonant-scattering, magnetic-scattering, and dichroism techniques earn no catalog Method today, so the Methods below render unlinked and are carried pending until a technique enters scope (`TECH-1`).

### Resonant elastic X-ray scattering

P09 tunes the incident energy onto an absorption edge (the DCM) and measures the elastically scattered intensity on the six-circle [goniometer](sample.md), with the [phase retarder](sample.md) setting incident polarization and the [analyzer](sample.md) resolving the scattered polarization.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant elastic X-ray scattering | `resonant_scattering` | edge-tuned elastic scattering on the six-circle diffractometer + PerkinElmer / Pilatus, with polarization analysis; reuses the `resonant_scattering` slug 4-ID / i06 / i10 share, a further consumer (`TECH-1`) |

### Magnetic scattering and dichroism

P09's MAG endstation applies a 14 T field to the sample and measures the magnetic scattering / dichroism, with the phase retarder switching incident polarization for XMCD.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Magnetic scattering | `magnetic_scattering` | scattering in the 14 T high-field magnet; reuses the `magnetic_scattering` slug, a further consumer (`TECH-1`) |
| X-ray magnetic circular / linear dichroism | `xmcd` | dichroism in the 14 T magnet with the phase retarder setting polarization; reuses the `xmcd` slug 4-ID / i06 / i10 share, a further consumer (`TECH-1`) |

### A polarization / magnetism beamline on the 4-ID vocabulary

P09 is the fleet's resonant-scattering and high-field-magnetism beamline. Its techniques are new to CORA's catalog (no resonant / magnetic Method is earned yet), but they reuse the slugs the APS 4-ID deployment and the Diamond i06 / i10 beamlines already carry pending, so none forces a new Method now. Crucially, the instrument anatomy reuses the polarization / magnetism Families 4-ID introduced: the phase retarder binds the catalog `PhaseRetarder` and the analyzer the catalog `PolarizationAnalyzer` (graduated across 4-ID / i10 / ID32 / P09, presenting Positioner), while the 14 T magnet binds the graduated catalog `Magnet` (earned across 4-ID + i10-1 + ID32), a further consumer. For `PhaseRetarder`, P09 was the rule-of-three signal (with P22) that earned it into the catalog. All recorded on [Model](#model).

### Not modelled yet

The concrete acquisition recipes (the energy / diffractometer / field scan sequences, the polarization-switching dichroism loops) are not written yet; they join as the deployment approaches the point where CORA drives P09. Whether the resonant / magnetic Methods enter CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P09, and the trust shape that will gate it. First cut.*

Governance at P09 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P09 is CORA's seventh PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P09 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P09, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals (across the three areas) and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

P09 also carries the hazard classes that come with a high-field magnetism endstation: a 14 T superconducting magnet and its liquid-helium cryogen, a stored-energy and field hazard that gates access to the MAG endstation. Those land with the instruments that bring them when the deployment firms up; the magnet is modelled as a sample-environment `Magnet` Asset, not a beam-steering device CORA drives.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P09, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P09 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P09 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P09 new

P09 is a seventh beamline at an existing Site, and the richest of the PETRA III set in technique breadth: resonant elastic X-ray scattering and HAXPES (MONO), diffraction (DIF), and high-field magnetism / XMCD (MAG, a 14 T magnet). At the modelling level it is the **second consumer of the polarization / magnetism vocabulary** the APS 4-ID deployment introduced: the phase retarder, the polarization analyzer, and the high-field magnet.

### No new families (the 4-ID vocabulary ports cleanly)

P09 coins no new Family. It binds the catalog `PhaseRetarder` Family (P09 was the second consumer, the rule-of-three signal with P22 that earned it into the catalog) and the graduated catalog `PolarizationAnalyzer` Family (earned across 4-ID / i10 / ID32 / P09, presenting Positioner) for its analyzer. Its 14 T magnet binds the graduated catalog `Magnet` Family (earned across 4-ID + i10-1 + ID32; presents `Regulator`), a further consumer. The diffractometers bind the catalog `Goniometer` Family (not the composed `Diffractometer` Assembly, the same call as P01 EH2); the optics bind `Monochromator` / `Mirror` / `Transfocator` / `Slit` / `Filter`; the sample environment binds `TemperatureController` / `Hexapod` / `LinearStage`; the detectors bind `Camera` / `EnergyDispersiveSpectrometer`. Nothing in the catalog changes.

### The control plane

P09 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines. Its instrument diversity is high (OMS / VME58 steppers, Galil slits, PI + AttoCube piezos, a hexapod; PerkinElmer / Pilatus / Andor detectors, the SIS3302 digitizer, GPIB instruments). The handles are read from P09's public OnlineXML registry and carried confirm (`CTRL-1`). The resonant-scattering / magnetism acquisition (the energy / diffractometer / field scan with polarization switching) runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, the same shape as the 4-ID seam.

### Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The OnlineXML exposes the gap, not the period; carried pending.
- **The optics detail (`OPT-1`).** The DCM crystal cut, the mirror coatings, and the CRL detail are carried confirm-pending.
- **The diffractometer structure (`DIFF-1`).** The MONO / DIF / MAG six-circle counts and detector arms are pending; modelled as `Goniometer` Assets, not `Diffractometer` Assemblies.
- **The motor-bank axis roles (`GROUP-1`).** The MONO / DIF `p09/motor` banks carry no per-axis role; grouped as stage Assets.
- **The polarization / magnet detail (`POL-1`, `MAG-1`).** The phase-retarder / analyzer geometry and the 14 T magnet field / control are pending; the polarization Families are the graduated catalog `PhaseRetarder` / `PolarizationAnalyzer`, and the magnet binds the graduated catalog `Magnet` Family (its per-Asset field / control detail pending).
- **The detector roster (`DET-1`).** The detector models and the SIS3302 channel count (collapsed from the registry's ROI explosion) are named, not fully bound.
- **The host mapping (`HOST-1`).** A shared Lambda reports on the bare `petra3` host; a stray `p07/hexapodsmall` row (a P07 device) is excluded from P09.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The resonant / magnetic Methods (`TECH-1`).** Whether they enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the existing slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p09_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P09 team to confirm before the model can be trusted.*

P09 was reverse-engineered from P09's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p09](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p09), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no crystal cuts, magnet field, or energy calibration. P09 is CORA's seventh PETRA III beamline and the second consumer of the 4-ID polarization / magnetism vocabulary. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a MONO optics-and-resonant-scattering hutch, a DIF diffraction hutch, and a MAG magnetism endstation? | A `p09-mono` hutch and `p09-dif` / `p09-mag` endstations, read from the OnlineXML host names. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; gap read, period pending. | The source Asset detail. |
| GROUP-1 | Nice-to-have | The per-axis roles of the MONO / DIF motor banks (`p09/motor/exp`, `p09/motor/dif`). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |
| HOST-1 | Nice-to-have | A shared Lambda detector reports on the bare `petra3` host, and the registry includes a `p07/hexapodsmall` row. Shared host / cross-beamline import? | The Lambda is noted unbound; the P07 device is excluded from P09. | The device-to-host mapping. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The DCM crystal cut, the mirror coatings, the CRL detail, and the absorber configuration. | A DCM `Monochromator`, two `Mirror`s, a `Transfocator` CRL, and `Filter` absorbers; physical detail pending. | The optics modelling. |

### Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-build | The diffractometer circle counts (MONO / DIF / MAG) and whether each composes a Diffractometer Assembly with a detector arm. | A `Goniometer` Asset per area (six-circle E6C), not the composed Diffractometer Assembly, until detector arms are confirmed. | The diffractometer modelling. |
| POL-1 | Nice-to-have | The phase-retarder geometry (circles + AttoCube fine axes) and the polarization-analyzer detail. | The catalog `PhaseRetarder` Family and the catalog `PolarizationAnalyzer` Family (graduated across 4-ID / i10 / ID32 / P09); detail pending. | The polarization-instrument modelling. |
| MAG-1 | Blocks-go-live | The MAG magnet field (14 T assumed), its cryogen, and its control / ramp interface. | A 14 T superconducting `Magnet` (the graduated catalog Family, a further consumer); field and control pending. | The per-Asset magnet field / control detail. |
| SAMPLE-1 | Nice-to-have | The MAG sample-hexapod and PI-piezo geometry. | A `Hexapod` + `LinearStage` piezos; geometry pending. | The MAG sample modelling. |
| TEMP-1 | Nice-to-have | The CryoCon / Lakeshore / LSCI sensor / setpoint handles. | `TemperatureController` controllers; cryogenic cooling. | The temperature-control modelling. |

### The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector roster per area, the PerkinElmer / Pilatus / Andor models, and the SIS3302 fluorescence channel count (collapsed from the registry's ROI explosion). | `Camera` area detectors plus an `EnergyDispersiveSpectrometer` SIS3302 / MCA; models pending. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P09 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent, the cooling / beam supplies, and the magnet liquid-helium supply. | Photon beam, cooling water, vacuum, and liquid helium. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do resonant scattering, magnetic scattering, and XMCD enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `resonant_scattering` / `magnetic_scattering` / `xmcd` slugs 4-ID / i06 / i10 share; none coined. | The technique Capabilities. |
