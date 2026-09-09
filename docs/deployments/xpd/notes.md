# Notes

## Techniques

*What CORA would run at XPD: powder-diffraction and total-scattering techniques, each a [Catalog](../../catalog/methods.md) Method. XPD is the NSLS-II twin of the Diamond [I11](../i11/notes.md#techniques) (powder diffraction) and [I15-1](../i15-1/notes.md#techniques) (total scattering / PDF) beamlines, and it follows their deferral exactly.*

XPD's techniques are powder diffraction and total scattering, a science domain Diamond's i11 and i15-1 brought to CORA as new Capabilities. As there, the Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Mode | Notes |
| --- | --- | --- |
| Powder diffraction | monochromatic, flat panel | Debye-Scherrer rings on the flat panel at a chosen energy; the i11 Capability, new Capability pending (TECH-1) |
| Total scattering / PDF | fixed high energy, close detector | wide-Q on the flat panel at a close detector distance; the i15-1 Capability, new Capability pending (TECH-1) |
| Variable-temperature diffraction | over a temperature ramp | the same, over a ramp on the sample-environment stages (TEMP-1) |
| Autonomous sample exchange | n/a | a Procedure over the spine, threaded through `Subject` custody and gated by a Clearance (ROBOT-1) |

All the scattering techniques need the [diffractometer and sample stages](sample.md), the [flat-panel detectors](detector.md), and the detector distance; the exposure shutter gates the frames.

### Why the Capabilities stay deferred

Diamond i11 and i15-1 opened the question of whether the powder-diffraction and total-scattering Capabilities enter CORA's catalog (TECH-1), and `main` deliberately left them pending: a powder or PDF measurement is a new science Capability binding device Roles that already exist (the flat panel presents Detector, the diffractometer and mono present Positioner), so what is new is the Capability, not a device shape. XPD reinforces the case for both at a second facility without coining either, the same earn-the-abstraction discipline the deferred `xpcs` (CHX), `scanning` (HXN), and `energy_scan` (BMM) Capabilities follow. Because the defining Capabilities are not in the catalog, XPD records **no Practice** in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here); the binding lands when the Capability does.

The azimuthal integration and pair-distribution-function reduction (the Fourier transform of the total-scattering structure function into a real-space PDF) are `ComputePort` work, not beamline Methods. The autonomous sample exchange reuses the i03 / i15-1 autonomous-loop shape: a Procedure over the spine, not a new device family (ROBOT-1).

## Governance

*Who may act at XPD and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An XPD beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start an acquisition, change the detector distance, run a temperature program, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

### High-throughput and the sample robot

XPD's strength is throughput: a sample-array stage and a sample-changing robot let it run many powders unattended, often across temperature ramps. That is where CORA's custody and trust shapes earn their keep. CORA would model the autonomous exchange as a Procedure over the spine, threaded through the `Subject` aggregate so each sample's identity and provenance is tracked, and gated by a Clearance, the same shape as the I03 macromolecular-crystallography loop and the I15-1 powder exchange (ROBOT-1). If an autonomous Agent were added to choose the next sample or decide when a pattern is good enough, it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.

## Model

*The developer's by-kind index: where each CORA aggregate's XPD content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at XPD |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (28-ID-A optics, 28-ID-C experiment) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring the other NSLS-II and Diamond beamlines. Left out on purpose:

- **No new Family.** XPD is a reuse-and-reinforce deployment, the NSLS-II twin of Diamond i11 (powder diffraction) and i15-1 (total scattering / PDF): the flat panels bind `Camera`, the flux counters `FluxMonitor`, the sample environment `TemperatureController` (which i11 graduated, reinforced here at a second facility), the double-Laue monochromator `Monochromator`, the mirror `Mirror`, the pinhole `Aperture`, the exposure shutter `Shutter`.
- **The graduated `PositionMonitor`.** The optics-hutch beam-position monitor binds the graduated catalog `PositionMonitor` Family that several APS and NSLS-II deployments share: it presents the `Sensor` Role, earned across the wide fleet that shares it, distinct from `FluxMonitor` by measuring beam position rather than flux. The per-Asset ion-chamber / quad-electrometer channel map stays open (DIAG-1), recorded in the promotion-review register.
- **No new Capability or Method.** Powder diffraction and total scattering sit on the deferred `powder_diffraction` / `total_scattering` Capabilities Diamond i11 and i15-1 left pending (TECH-1); XPD reinforces both without coining either and records no Practice. The azimuthal integration and PDF reduction are `ComputePort` work.
- **The autonomous sample robot.** Modelled as a deferred Procedure over the spine threaded through `Subject` custody (ROBOT-1), reusing the i03 / i15-1 autonomous-loop shape, not a new device family.
- **The high-resolution channel** alongside the modelled main PDF channel: the high-resolution monochromator (`Mono:HRM`, in the 28-ID-C hutch) and the downstream high-resolution endstation (28-ID-D) are noted and deferred together (ENDSTATION-1), the way SRX deferred its micro endstation and 32-ID modelled one of several instruments.
- **The calibration diffractometer (`Dif:2`)** and its Ecal wavelength-calibration routine (scanning against a standard to fit the beam wavelength) are a routine powder/PDF operation, deferred to a named question (CALIB-1) rather than modelled at this design phase. The dormant multi-analyzer stage (`MAD:DMS`) and the mono beam-defining slits (`Slt:MB1` / `Slt:MB2`) are deferred alongside it.
- **The in-situ / operando accessories**: a QEPro UV-Vis spectrometer read in parallel with the diffraction pattern (a distinct optical-spectroscopy modality, not a `Camera`), the gas switcher, and the flash-sintering / electrochemistry power system, deferred to a named question (OPERANDO-1); the UV-Vis channel would need its own family decision when it lands.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the XPD team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/xpd-profile-collection`](https://github.com/NSLS2/xpd-profile-collection) profile collection): the EPICS PVs are read from it, but vendor identities, physical positions, and the source and endstation configuration are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The source: 28-ID is a damping-wiggler beamline, but no source PV or parameters are in the profile collection. | An insertion-device (damping wiggler), identity-only, no PV. | The Source Asset PV and settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the endstation exposure shutter (`XF:28IDC-ES:1{Sh:Exp}`) is in source, not the front-end PPS leaves. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENDSTATION-1 | Nice-to-have | The high-resolution channel: the high-resolution monochromator (`Mono:HRM`, in the 28-ID-C hutch) and the downstream high-resolution endstation (28-ID-D) with its own sample stack (the `Stg:Stack` fine axes) and a third flat panel (`Det:PE3`). | The main PDF channel (DLM mono + 28-ID-C endstation) is modelled; the high-resolution channel is noted, deferred. | The HRM and 28-ID-D Assets. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The double-Laue monochromator crystal and energy range, and the high-resolution monochromator crystal. Both (`Mono:DLM`, `Mono:HRM`) are in source. | Two Monochromator Assets, settings blank. | The Monochromator settings. |
| ENERGY-1 | Nice-to-have | Does XPD ever scan energy as the measurement, or is it always fixed-energy per experiment? | Fixed-energy; energy_scan not modelled. | The energy Capability decision. |

### Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The full diffractometer axis set behind `Dif:1`, and whether the goniometric axes warrant a `Goniometer` plus a Diffractometer Assembly (the 8-ID / i11 precedent). | A `LinearStage` sample stack, rotation axes and the Assembly deferred. | The SampleStage axes and orientation modelling. |
| DET-1 | Blocks-go-live | Which flat panels are live (PerkinElmer pe1 / pe2, Dexela, the 28-ID-D pe3) vs the spare set, and the detector distance range. | pe1 primary, Dexela secondary; all Cameras; distance range blank. | The detector roster and Q-range. |
| TEMP-1 | Nice-to-have | Which sample-environment units are live (Cryostream cs700 / cs800, Eurotherm, hot-air blower, Lakeshore cryostat, Linkam furnace)? | One `TemperatureController` Asset (the Cryostream); the others noted. | The sample-environment Assets. |
| DIAG-1 | Nice-to-have | The ion-chamber and quad-electrometer channel map (which channel is I0); the `PositionMonitor` Family is settled (graduated catalog Family presenting `Sensor`), so only this per-Asset channel map stays open. | Read-only flux counters (`FluxMonitor`), the graduated catalog `PositionMonitor`; channel map blank. | The IonChamber / QuadElectrometer bindings. |
| CALIB-1 | Nice-to-have | The energy / wavelength calibration: the calibration diffractometer (`Dif:2`: `th_cal`, `tth_cal`, `ecal_x`, `ecal_y`) and the Ecal routine that scans a standard to fit the beam wavelength, plus the dormant multi-analyzer stage (`MAD:DMS`) and the mono beam-defining slits (`Slt:MB1` / `Slt:MB2`). | A Procedure over the spine; these support devices deferred at this design phase. | The calibration Procedure and its devices. |
| OPERANDO-1 | Nice-to-have | The in-situ / operando accessories: the QEPro UV-Vis spectrometer read in parallel with the diffraction pattern (a distinct optical-spectroscopy modality, not a `Camera`), the gas switcher (`Env:02`), and the flash-sintering / electrochemistry power system. | Deferred; the UV-Vis channel needs its own family decision when it lands. | The operando detector and sample-environment Assets. |
| ROBOT-1 | Nice-to-have | The sample-changing robot (`XF:28IDC-ES:1{SM}`): CORA would model autonomous powder / capillary exchange as a Procedure over the spine threaded through the `Subject` aggregate and gated by a Clearance, the same shape as the I03 MX loop and the I15-1 powder exchange. | The robot is deferred autonomous-loop machinery, not a beam-path Asset. | The sample-handling Procedure and Subject custody thread. |

### Controls

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, IPs. | Families bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the powder-diffraction and total-scattering / PDF Capabilities enter CORA's catalog, or stay deferred? This is the same owner-scope decision Diamond i11 and i15-1 opened. | Capabilities deferred (rendered unlinked), no Practice recorded. | The powder / PDF Capability scope. |
