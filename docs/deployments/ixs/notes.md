# Notes

## Techniques

*What the modelled part of IXS is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md) is how a facility adapts it. IXS's technique is momentum-resolved hard X-ray inelastic scattering, the fleet's first energy-loss method, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

### Momentum-resolved inelastic X-ray scattering

IXS sets the momentum transfer Q with the six-circle reciprocal-space arm, then scans the incident energy against a fixed crystal analyzer and counts the energy-analyzed scattered photons, so the measurement is the intensity surface I(Q, energy-loss): how much energy the sample exchanges with the photon at a chosen momentum transfer. The energy loss is read as the difference between the scanned incident energy and the fixed final energy the analyzer passes.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Momentum-resolved inelastic X-ray scattering | `inelastic_scattering` | Q is set on the [six-circle spectrometer arm](detector.md) via the H/K/L reciprocal-space pseudo-axis; the incident energy is scanned on the [double-crystal and high-resolution monochromators](source.md) against the fixed [crystal energy analyzer](detector.md); the energy-analyzed signal is point-counted on the electrometers; Method not yet in catalog |

It needs the [incident-energy chain](source.md) (the DCM for the coarse energy and the high-resolution monochromator for the meV steps), the [sample stage](sample.md), and the [six-circle arm, crystal energy analyzer, and counting detectors](detector.md). The arm scattering angle sets the magnitude of the momentum transfer; the analyzer fixes the final energy so the incident-energy scan reads out the energy loss.

### A new operating axis for the fleet

Energy loss is genuinely new for the fleet. The catalog already covers elastic scattering (SAXS/WAXS, XPDF, powder, XPCS, MX), XRF microprobe, hard X-ray absorption (BMM), and soft resonant inelastic scattering (SIX), but no hard inelastic scattering. The new axis is the acquisition shape itself: scan one optic (the incident energy) against a second, fixed energy-selecting optic (the crystal analyzer) while a point detector counts, rather than expose an area detector at one energy. That is a new Capability, deferred as a question (`TECH-1`); it forces no new device families beyond the loose [`EnergyAnalyzer`](#new-loose-families).

### Not modelled yet

The concrete acquisition recipes (the incident-energy maps, the per-Q energy scans, the analyzer alignment, and the counting times) are not written yet; they join as the deployment approaches the point where CORA drives IXS. Whether the technique enters CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); hard inelastic scattering is a new regime for the fleet (see [Open questions](#open-questions) for the world-facts to confirm first).

## Governance

*Who will act at IXS, and the trust shape that will gate it. First cut.*

Governance at IXS follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

IXS is not yet driven by CORA, so this shape is not yet instantiated. As a modelling-exercise scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. The profile collection exposes only coarse queue-server groups, not the human roster, so the NSLS-II operator and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md), shared with the rest of the fleet (`GOV-1`).

The safety tier is the other piece that is not yet settled. The PSS search-and-secure permit signals and the front-end and photon shutters are absent from the beamline's profile collection, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md), not on the beamline, and the beamline links up to them. IXS adds the hazard classes that come with a hard X-ray endstation under vacuum and a temperature-stabilized crystal analyzer; those land with the instruments that bring them, and an experiment Clearance would carry them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives IXS, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's IXS content lives, the one new loose family this first hard inelastic-scattering deployment introduces, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at IXS |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the reciprocal-space `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes IXS new

IXS is CORA's first photon-in / photon-out energy-LOSS technique. The fleet already has elastic scattering (SAXS/WAXS, XPDF, powder, XPCS, MX), XRF microprobe, hard X-ray absorption (BMM), and soft resonant inelastic scattering (SIX), but no hard inelastic scattering. The novelty is the acquisition shape: set the momentum transfer Q with a six-circle reciprocal-space pseudo-axis, then scan the incident energy (the DCM, and the high-resolution monochromator for meV steps) against a fixed crystal analyzer, point-detecting the energy-analyzed scattered beam to build I(Q, energy-loss). That is a new Capability, deferred as a question (TECH-1); it forces no new device families beyond the analyzer below.

### New loose families

IXS introduces one device class no existing catalog Family covers: the crystal energy analyzer. Per earn-the-abstraction, it is held **loose at n=1** and graduates nothing: a second independent hard crystal-analyzer beamline must earn the abstraction before any catalog change. The name was cleared by the naming-r3 gate.

| Loose family | Presents (when graduated) | What it is | Earns when |
| --- | --- | --- | --- |
| `EnergyAnalyzer` | Positioner (Sensor-vs-Positioner a confirm) | a diced multi-crystal Bragg analyzer that selects the final photon energy of the scattered beam, focusing energy-selected photons onto the point detectors | a 2nd hard crystal-analyzer / IXS beamline (`ANALYZER-1`) |

`EnergyAnalyzer` is deliberately not stretched onto an existing Family. It is not the catalog `EnergyDispersiveSpectrometer` (a per-event point Sensor that reads energy, where the analyzer positions crystals and the reading happens downstream at the electrometers), nor the catalog `Monochromator` (an upstream incident-beam optic), nor the catalog `SpectrometerArm` (the energy-dispersive arm SIX coined, since graduated; IXS uses a driven scanning crystal analyzer, not a dispersive one). naming-r3 chose `EnergyAnalyzer` over `Analyzer` and `CrystalAnalyzer`: it is the `<Quantity>Analyzer` sibling of the catalog `PolarizationAnalyzer` (the qualifier names the analyzed quantity), and it avoids the `CrystalAnalyzer` / `AnalyzerCrystal` read-aloud homograph. Whether `EnergyAnalyzer` and `PolarizationAnalyzer` later merge into one `Analyzer` Family differentiated by a setting is the open `ANALYZER-1`, a gate decision at the second sighting, not this PR's.

### Deliberately not here yet

- **The six-circle arm binds the catalog `Goniometer`, not a new family.** The spectrometer arm (tth / th / chi / phi driven by the H/K/L reciprocal-space pseudo-axis) is the 8-ID / 4-ID six-circle diffractometer anatomy. In descriptor mode it binds the catalog `Goniometer` directly (the 8-ID / 4-ID scaffold pattern), and SIX's dispersive `SpectrometerArm` is the wrong anatomy for a driven scanning arm. The reciprocal-space layer binds the catalog `PseudoAxis`.

- **The analyzer-Assembly question (`ANALYZER-1`).** Whether the crystal analyzer plus the six-circle arm compose an `Assembly(Diffractometer)`-style Fixture is deferred, exactly as 8-ID and 4-ID deferred materializing their diffractometer Assemblies in descriptor mode. The first cut is a flat loose `EnergyAnalyzer` Asset plus a `Goniometer` arm Asset, with the Assembly named as the follow-on. An Assembly is earned at n=2 across independent beamlines; coining one at n=1 would be over-modelling.

- **The diced-crystal identity (`XTAL-1`).** The six diced crystals each carry their own theta / phi and PID temperature, so each is identity-bearing. The lower-risk first cut carries them as settings on the one `EnergyAnalyzer` Asset; promoting each to a child Asset via `parent_id` is exactly the nested-component-identity convention, which is itself at a rule-of-three gate (applied only for `RotaryDriveChassis` so far), so IXS flags `XTAL-1` as a candidate trigger rather than asserting it. The six crystal-temperature PID loops are carried as one `TemperatureController` Asset for the same reason (`TEMP-1`).

- **The high-resolution-mono beamstop (`HRM-1`).** The high-resolution monochromator carries an in-line beamstop; whether it is a distinct child `BeamStop` Asset is gated under the same nested-component rule-of-three.

- **The IXS Method.** Whether momentum-resolved inelastic scattering enters CORA's catalog as a Capability / Method is an owner decision; the Practice renders unlinked, pending (`TECH-1`).

- **The simulated devices and full asset-tree scenarios.** No `test_ixs_*.py` registers the IXS asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the IXS team to confirm before the model can be trusted.*

IXS was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/ixs-profile-collection](https://github.com/NSLS2/ixs-profile-collection)), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from the `startup/*.py` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet), including the new loose `EnergyAnalyzer` family). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | Does 10-ID share a canted straight with a sibling beamline, or run off its own undulator in series? | One root Unit Asset `IXS` on its own straight. | The source topology in the [descriptor](index.md). |
| ENC-1 | Blocks-go-live | Are the PV zones `XF:10IDA/B/C/D` four separate shielded hutches or beam zones within fewer hutches? | Four enclosures, one per zone. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The IVU22 undulator period and type. | An in-vacuum undulator on `SR:C10-ID:G1{IVU22:1}`, period carried pending. | The source Asset detail. |

### Source and optics

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

### Sample and spectrometer

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | Are the sample table (`Spec:1`) and the sample-environment translations (`Env:1`) one fused stage or two siblings, and what is mounted on them? | Two sibling `LinearStage` Assets on their separate PV roots. | The sample-stage modelling. |
| ANALYZER-1 | Blocks-build | How is the crystal energy analyzer configured: the diced-crystal Bragg geometry, the analyzed final energy, and whether it shares mechanics with the six-circle arm? | A diced multi-crystal Bragg analyzer on the spectrometer arm, selecting a fixed final energy. | The analyzer geometry; the CORA structural modelling is on [Model](#deliberately-not-here-yet). |
| XTAL-1 | Blocks-go-live | Are the six diced analyzer crystals individually addressed (each its own theta / phi and temperature loop), and do they act as one analyzer? | Six crystals, each with theta / phi and a PID temperature, acting as one analyzer. | The diced-crystal addressing; the child-Asset modelling is on [Model](#deliberately-not-here-yet). |
| TEMP-1 | Nice-to-have | Are the six crystal-temperature PID loops one Asset or six, and do they parent to the analyzer or to per-crystal child Assets? | One `TemperatureController` Asset noting six PID channels. | The thermal-control modelling. |

### Detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The electrometer / scaler channel map: which channels are the analyzed-signal detector, which is I0, and whether the analyzer-focus photodiode is a separate Asset or a channel. | Quad electrometers + the scaler I0 bound to `FluxMonitor`; the focus diode is a channel, not a standalone Asset. | The detector modelling. |
| ENERGY-1 | Nice-to-have | The read-only derived diffractometer angles (`HKLDerived`) present the Sensor read-back facet, not a driven axis. | A read-back facet of the reciprocal-space `PseudoAxis`. | The pseudo-axis read modelling. |
| DIAG-1 | Blocks-go-live | The beam-position monitors bind the graduated catalog `PositionMonitor` Family; what beam-center calibration and diagnostic-foil channel detail do they need? | The graduated catalog `PositionMonitor` (presents `Sensor`, distinct from `FluxMonitor` by measuring beam position rather than flux), the NSLS-II sibling choice; beam-center and foil channels to supply. | The beam-position-monitor calibration and channel detail. |
| BPM-1 | Nice-to-have | Which monitors are true beam-position monitors versus intensity (I0) normalizers? | Treated as beam-position monitors; the intensity ones would be `FluxMonitor`. | The position-vs-intensity split. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the ixs-profile-collection current and correct? | The handles in the descriptor are taken from the profile collection and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the front-end / photon shutters (absent from the profile collection). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the NSLS-II Site, not instantiated per beamline. | The governance principals. |
| SUP-1 | Nice-to-have | The vacuum extent and the analyzer thermal-stabilization supply. | Photon beam, cooling water, and vacuum on the optics and spectrometer path. | The Supply observations. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Does the momentum-resolved inelastic-scattering technique enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice, no `cora.capability.ixs` coined. | The IXS Capability. |
