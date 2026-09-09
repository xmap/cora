# Notes

## Techniques

*What CORA would run at ISS: X-ray absorption and X-ray emission spectroscopy, each a [Catalog](../../catalog/methods.md) Method. ISS follows the deferral discipline of the beamlines that brought spectroscopy to CORA.*

ISS's measurement is energy spectroscopy: it sweeps the incident energy across an absorption edge (EXAFS) and, with the crystal emission spectrometers, resolves the emitted spectrum (XES) or selects an emission line during the incident-energy sweep (HERFD). The Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Mode | Notes |
| --- | --- | --- |
| X-ray absorption (EXAFS) | transmission / fluorescence, energy fly-scan | I0 / It / Ir ion chambers or the Xspress3 SDD over a trajectory energy sweep; the BMM energy-scan question (ENERGY-1, TECH-1) |
| X-ray emission (XES) | emission spectrometer, fixed incident energy | the Johann or von Hamos crystal spectrometer disperses the emitted spectrum onto the area detector (SPEC-1, TECH-1) |
| HERFD | emission spectrometer, incident-energy fly-scan | high-energy-resolution fluorescence detection: scan the incident energy, read one emission line through the analyzer (ENERGY-1, SPEC-1) |

All three need the [sample stage](sample.md) and a [detector](detector.md); the trajectory fly-scan sweeps the energy and the analog pizza box reads the detectors synchronously.

### Why the Method scope stays pending

ISS's absorption and emission both lean on energy spectroscopy CORA carries pending. EXAFS is the energy-sweep-as-the-measurement case BMM raised: the `energy_scan` Capability is anticipated in the catalog but deferred until a conduct-path forces it (ENERGY-1), and a descriptor scaffold does not force it; ISS is a further consumer that strengthens the case without coining it. The emission techniques (XES, HERFD) are the same shape LCLS-MFX left pending as the `xas_spectroscopy` Method (XAS / XES via the emission spectrometer), so ISS **reuses** that Method as the second consumer rather than coining a new one (TECH-1), and records that one pending Practice on the [NSLS-II Site](../nsls2/index.md). The device Roles already exist (the ion chambers present Sensor, the SDD the energy-dispersive Sensor, the emission spectrometers the Detector Role); what is new is the science Method, not a device shape.

The per-technique reduction (EXAFS normalization and fitting, XES / HERFD spectra) is `ComputePort` work, not beamline Methods.

## Governance

*Who may act at ISS and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An ISS beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may load an energy trajectory, sweep the energy, start an acquisition, move the emission-spectrometer crystals, run an in-situ program, override a caution, or commit an energy calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

### The energy-scan under custody

ISS's defining operation is the trajectory energy fly-scan, which couples the monochromator, the encoder, and the streaming detectors as one timed sweep. CORA's Campaign and Trust shapes are where that resolves: loading and starting a trajectory is a command the trust boundary gates, and the per-scan energy calibration (the reference foil read on the reference ion chamber) is a committed fact under custody, not an ad-hoc adjustment. If an autonomous Agent were added to drive the EXAFS / HERFD program (a common pattern at high-throughput XAS beamlines), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.

## Model

*The developer's by-kind index: where each CORA aggregate's ISS content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at ISS |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (8-ID-A optics, 8-ID-B experiment) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What this deployment graduates

ISS earns one catalog change: the **`EmissionSpectrometer`** Family GRADUATED. LCLS-MFX introduced it for its von Hamos six-crystal XES spectrometer and carried it loose at n=1 (SPEC-1, with MAX IV Balder noted as a near-sighting). ISS's Johann and von Hamos crystal emission spectrometers are the **second** sighting, earning the rule-of-three the way `GratingMonochromator` (CSX), `Manipulator` (ESM), and `ElectronAnalyzer` (SST) graduated at their second sighting. The abstraction is settled (a crystal-analyzer emission spectrometer composing analyzer crystals and a 2D detector along a Rowland-circle or wavelength-dispersive geometry is a distinct, recurring device, not a point Sensor and not a beam-conditioning Monochromator), so it GRADUATED into the catalog (SPEC-1); LCLS-MFX's references were swept loose to graduated alongside. It stays distinct from the still-loose `EnergyAnalyzer` (the IXS diced-crystal energy-selecting analyzer, ANALYZER-1), which graduates nothing until its own rule-of-three, and from the catalog `SpectrometerArm` (the SIX soft X-ray grating dispersive RIXS arm, since graduated across SIX + ID32 + ID28, RIXS-1).

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring the other NSLS-II and Diamond beamlines. Left out on purpose:

- **No new loose Family.** ISS is otherwise a reuse deployment: the trajectory and high-resolution monochromators bind `Monochromator`, the mirrors `Mirror`, the filter box `Filter`, the slits `Slit`, the shutters `Shutter`, the energy axis `PseudoAxis`, the sample stage `LinearStage`, the goniometer `Goniometer`, the reference foil wheel `RotaryStage`, the thermal stage `TemperatureController`, the ion chambers `FluxMonitor`, the Xspress3 SDD `EnergyDispersiveSpectrometer`, the Pilatus `Camera`, the trajectory controller `MotionController`, the analog pizza box `TimingController`.
- **The graduated `PositionMonitor`.** The beam-position diagnostics bind the graduated catalog `PositionMonitor` Family that the wide fleet shares; it presents the `Sensor` Role, earned across that fleet, distinct from `FluxMonitor` by measuring beam position rather than flux. The per-Asset beam-position channel map is the residual (`DIAG-1`).
- **No new Capability or Method.** EXAFS leans on the deferred `energy_scan` Capability (ENERGY-1, the BMM question; ISS strengthens it as a further consumer without forcing it); XES / HERFD reuse the `xas_spectroscopy` Method LCLS-MFX left pending, the second consumer (TECH-1). ISS records that one pending Practice and coins nothing. The per-technique reduction is `ComputePort` work.
- **The deferred in-situ environment.** The ion-chamber fill-gas mass-flow controllers (He / N2) would bind the graduated `FlowController` Family, but they and the broader in-situ sample environment are named in a question (`ENV-1`) rather than modelled at this design phase. ISS models the main transmission / fluorescence / emission legs as the representative configuration.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the ISS team to confirm. This model is reverse-engineered from public open source (the `NSLS2/iss-profile-collection` bluesky / ophyd startup files): the EPICS PVs are read from the `startup/*.py` device classes, but undulator parameters, crystal cuts, vendor identities, and physical positions are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The 8-ID insertion-device identity, period, and gap range. The profile collection drives photon energy through the HHM trajectory and does not expose the undulator gap PVs; only the ring current (`SR:OPS-BI{DCCT:1}`) is read. | An in-vacuum undulator on the 3 GeV ring, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the shutters (`XF:08ID-PPS{Sh:FE}`, `XF:08IDA-PPS{PSh}`) are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The HHM and HRM crystal cuts, reflections, and energy ranges. Both monochromators (`Mono:HHM`, `Mono:HRM`) and the HHM trajectory controller (`MC:06`) are in source. | One trajectory DCM and one high-resolution mono Asset, crystal settings blank. | The Monochromator settings. |
| ENERGY-1 | Nice-to-have | ISS's measurement sweeps the energy axis (EXAFS) as a trajectory fly-scan, the textbook case for the energy-scan Capability the catalog anticipates. Does CORA coin `energy_scan` now, or keep it deferred until a conduct-path forces it? | Energy-scan deferred (the BMM question); ISS is a further consumer that strengthens the case. | The energy-scan Capability decision. |

### Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SPEC-1 | Blocks-go-live | The Johann and von Hamos crystal emission spectrometer geometry: the analyzer crystal cut, the Rowland-circle radius, and whether each of the (Johann: main + four auxiliary) analyzer crystals is a child Asset or a setting on the one spectrometer Asset. | Two `EmissionSpectrometer` Assets (catalog Family, graduated at this 2nd sighting after LCLS-MFX); crystals as settings for now. | The emission-spectrometer model and analyzer-crystal composition. |
| DET-1 | Blocks-go-live | The detector roster: the ion-chamber channel map (I0 / It / Ir / If through the ICAmplifier / Keithley-428 amps and the analog pizza box), the Xspress3 element count and ROI map, and which Pilatus serves which spectrometer. | The ion chambers, the 4-channel Xspress3, and one Pilatus modelled; channel maps blank. | The detector roster and channel maps. |
| TEMP-1 | Nice-to-have | Which sample-environment thermal units are live (the Lakeshore 331 is in source; cryostat / furnace not). | One `TemperatureController` Asset; the others noted. | The sample-environment Assets. |
| ENV-1 | Nice-to-have | The ion-chamber fill-gas flow (He / N2 mass-flow controllers `XF:08IDB-OP{IC}FLW:`) and the broader in-situ sample environment. The mass-flow controllers would bind the graduated FlowController Family; the broader environment is deferred at this design phase. | Deferred; fill gas and in-situ environment named here, not modelled. | The fill-gas and in-situ Assets. |
| DIAG-1 | Nice-to-have | The beam-position channel map (the Prosilica BPM cameras and the sample-positioner cameras); the `PositionMonitor` Family is settled (graduated catalog Family presenting `Sensor`, distinct from `FluxMonitor` by measuring beam position rather than flux). | Read-only beam-position (graduated catalog `PositionMonitor`) probes; channel map blank. | The PositionMonitor bindings. |

### Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, and IPs (the Delta-Tau HHM trajectory controller `MC:06`, the von Hamos `MC:3-Ax:` axes, and the EPICS motor records). | Families bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the X-ray absorption (EXAFS) and X-ray emission (XES / HERFD) techniques enter CORA's catalog as Methods, or stay pending? ISS reuses the `xas_spectroscopy` Method LCLS-MFX left pending, the second consumer. | The `xas_spectroscopy` Method reused pending; no new Method coined (the BMM / SST deferral discipline). | The technique Method scope. |
