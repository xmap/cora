# Open questions

*What CORA needs the IXS team to confirm before the model can be trusted.*

IXS was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/ixs-profile-collection](https://github.com/NSLS2/ixs-profile-collection)), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from the `startup/*.py` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet), including the new loose `EnergyAnalyzer` family). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | Does 10-ID share a canted straight with a sibling beamline, or run off its own undulator in series? | One root Unit Asset `IXS` on its own straight. | The source topology in the [descriptor](inventory.md). |
| ENC-1 | Blocks-go-live | Are the PV zones `XF:10IDA/B/C/D` four separate shielded hutches or beam zones within fewer hutches? | Four enclosures, one per zone. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The IVU22 undulator period and type. | An in-vacuum undulator on `SR:C10-ID:G1{IVU22:1}`, period carried pending. | The source Asset detail. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state IXS reads (current, fill, top-up). | Observe-only machine state on `SR:OPS-BI{DCCT:1}`, a loose `StorageRing`. | The machine-state observation. |
| FEEDBACK-1 | Nice-to-have | How should the source-orbit feedback (`SR:UOFB`) be modelled, if at all? | Carried family-less, modelling deferred (the i03 `XBPMFeedback` precedent). | The feedback Asset. |
| MONO-1 | Blocks-go-live | The DCM crystal cut / d-spacing, the incident-energy range, and the energy pseudo-axis partition rule. | Si(111) DCM, range 7.835-17.7 keV, energy via the DCM Bragg angle coupled to the undulator gap. | The monochromator and incident-energy Assets. |
| HRM-1 | Blocks-go-live | The high-resolution monochromator crystals, its meV resolution, and whether its in-line beamstop is a distinct identity-bearing Asset. | A second crystal `Monochromator` Asset; the beamstop carried as a note, not yet a child Asset. | The high-resolution mono Asset. |
| OPT-1 | Nice-to-have | The mirror coatings, bend mechanisms, and axis roles (VFM / HFM). | Grazing-incidence focusing mirrors bound to `Mirror`; coatings pending. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The blade-axis roles of each slit (front-end, DCM, SSA, transport, endstation, analyzer). | Four-blade variable openings bound to `Slit`. | The slit Asset detail. |
| PH-1 | Nice-to-have | Is the focusing pinhole a positioned beam-shaping aperture (`Aperture`) or a plain fixed opening (`Mask`)? | Bound to `Aperture` on the round-opening precedent; the catalog wording leans `Mask`. | The pinhole Family. |
| MCM-1 | Nice-to-have | Is the MCM optics manipulator six coupled parallel-kinematics axes (a `Hexapod`) or independent serial rotations? | A coupled six-DOF `Hexapod`. | The manipulator Family. |

## Sample and spectrometer

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | Are the sample table (`Spec:1`) and the sample-environment translations (`Env:1`) one fused stage or two siblings, and what is mounted on them? | Two sibling `LinearStage` Assets on their separate PV roots. | The sample-stage modelling. |
| ANALYZER-1 | Blocks-build | How is the crystal energy analyzer configured: the diced-crystal Bragg geometry, the analyzed final energy, and whether it shares mechanics with the six-circle arm? | A diced multi-crystal Bragg analyzer on the spectrometer arm, selecting a fixed final energy. | The analyzer geometry; the CORA structural modelling is on [Model](model.md#deliberately-not-here-yet). |
| XTAL-1 | Blocks-go-live | Are the six diced analyzer crystals individually addressed (each its own theta / phi and temperature loop), and do they act as one analyzer? | Six crystals, each with theta / phi and a PID temperature, acting as one analyzer. | The diced-crystal addressing; the child-Asset modelling is on [Model](model.md#deliberately-not-here-yet). |
| TEMP-1 | Nice-to-have | Are the six crystal-temperature PID loops one Asset or six, and do they parent to the analyzer or to per-crystal child Assets? | One `TemperatureController` Asset noting six PID channels. | The thermal-control modelling. |

## Detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The electrometer / scaler channel map: which channels are the analyzed-signal detector, which is I0, and whether the analyzer-focus photodiode is a separate Asset or a channel. | Quad electrometers + the scaler I0 bound to `FluxMonitor`; the focus diode is a channel, not a standalone Asset. | The detector modelling. |
| ENERGY-1 | Nice-to-have | The read-only derived diffractometer angles (`HKLDerived`) present the Sensor read-back facet, not a driven axis. | A read-back facet of the reciprocal-space `PseudoAxis`. | The pseudo-axis read modelling. |
| DIAG-1 | Blocks-go-live | How are the beam-position monitors modelled: the loose `BeamPositionMonitor` (the NSLS-II sibling choice), or `Diagnostic` / `GenericProbe`? | The loose `BeamPositionMonitor`, the hxn NSLS-II-sibling choice. | The diagnostics Family. |
| BPM-1 | Nice-to-have | Which monitors are true beam-position monitors versus intensity (I0) normalizers? | Treated as beam-position monitors; the intensity ones would be `FluxMonitor`. | The position-vs-intensity split. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the ixs-profile-collection current and correct? | The handles in the descriptor are taken from the profile collection and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the front-end / photon shutters (absent from the profile collection). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the NSLS-II Site, not instantiated per beamline. | The governance principals. |
| SUP-1 | Nice-to-have | The vacuum extent and the analyzer thermal-stabilization supply. | Photon beam, cooling water, and vacuum on the optics and spectrometer path. | The Supply observations. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Does the momentum-resolved inelastic-scattering technique enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice, no `cora.capability.ixs` coined. | The IXS Capability. |
