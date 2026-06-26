# Open questions

*What CORA needs the XFP team to confirm before the model can be trusted.*

XFP was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/xfp-profile-collection](https://github.com/NSLS2/xfp-profile-collection)), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from the `startup/` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are the optics (FE:C17B, XF:17BM-OP / XF:17BMA-OP) and the endstations (XF:17BMA-ES:1, ES:2) separate hutches? | Two enclosures: a `xfp-optics` zone and the `xfp-endstation` hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The 17-BM source (a bending magnet is implied by the name and the white-beam design; the profile collection exposes no source device, only ring current). | A bending-magnet source, observed only through the machine state. | The source Asset detail. |
| WHITE-1 | Blocks-go-live | Is routine footprinting white beam or pink beam (filtered by the mirror cutoff and the Al filters), and is there any monochromator in the footprinting path? (A DCM exists only on a separate XAS endstation, ES:3, excluded here.) | White / pink beam, no monochromator in the footprinting path; ES:3 out of scope. | The beam-conditioning model. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state XFP reads (only the ring current is read for a beam-present suspender). | Observe-only machine state, a loose `StorageRing`; the rest pending. | The machine-state observation. |
| OPT-1 | Nice-to-have | The front-end mirror coating and bend mechanism (a bendable mirror with a Bend focus axis and thermocouples). | A bendable focusing `Mirror`; coating and bend pending. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The blade-axis roles of the white-beam, PB / PDS, and ADC defining slits (the ADC horizontal gap sets the HTFly exposure window). | Four-blade / center-gap slits bound to `Slit`. | The slit Asset detail. |
| ATTN-1 | Blocks-go-live | The attenuation chain that sets the dose RATE: the eight-position Al filter wheel, plus the intermittently-connected 0-9 mm Al z-attenuator and the beam-defining pinhole apertures. | The filter wheel binds `Filter`; the pinhole / z-attenuator are further attenuators carried pending. | The dose-rate attenuator modelling. |

## Dose delivery

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DOSE-1 | Blocks-go-live | The dose-delivery chain: the timed shutters (the EPS pre-shutter, the PPS photon shutter, the inner DIODE sample shutter), the DG535 delay generator that fires the millisecond Uniblitz fast shutter (its opening-time setpoint is the dose time), and the flux-to-absorbed-dose calibration (which lives in offline analysis). | Seconds-scale dose is software-timed on the pre-shutter (`Shutter`); millisecond dose is the delay-generator-fired Uniblitz (`TimingController`); the dose calibration is offline. | The dose-delivery modelling. |

## Sample and delivery

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The capillary-flow sample stage axes and how a flowing solution capillary mounts in the beam. | A `LinearStage` for the capillary-flow stage; the flow is the fluidic seam. | The sample-stage modelling. |
| HT-1 | Blocks-go-live | The high-throughput modes: the 96-well plate stage and addressing (8 columns x 12 rows, addressed in pure Python with a coordinate table, no robot and no PV), and the shutterless HTFly stage (exposure = defining-slit gap over stage velocity). | `LinearStage` stages; the well addressing and the HTFly dose-timing are Procedures over the spine plus a Subject custody thread. | The high-throughput modelling. |
| FLOW-1 | Nice-to-have | The sample-delivery pumps (an M50 pump and a PHD2000 infusion pump, both with rate / volume setpoints) and whether the pump actuator earns a Family. | The pump binds the existing loose `FlowController` (i22 / 7-BM / LIX, n=4, graduation overdue); no new family coined. | The pump modelling; the CORA decision is on [Model](model.md#deliberately-not-here-yet). |
| FC-1 | Nice-to-have | The fraction collector (a PV-bound aliquot-routing actuator: a collect / waste valve, a tube index, a fill pattern) that captures footprinted aliquots, and whether it earns a Family. | Carried in the sample-custody seam (the footprinted-sample hand-off to offline MS); no `FractionCollector` Family coined at n=1. | The fraction-collector modelling. |
| SUBJECT-1 | Nice-to-have | The solution Subject: a biological macromolecule (protein / nucleic acid) in a buffer, irradiated, with its own provenance. | A liquid Subject; the footprinted aliquot is the run's output, carried to offline MS. | The Subject modelling. |
| TEMP-1 | Nice-to-have | The temperature / bias diagnostics (the SR630 thermocouple monitor and the Sydor bias / thermocouple controller), used as alignment-flux proxies. | Read-only diagnostics, not core footprinting devices; deferred. | The temperature-diagnostic modelling. |

## Detection and readout

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The flux / dose monitors: the QuadEM electrometers (incident flux plus a per-exposure time-series), the DIODE PDM array-logger, and which channels measure the delivered dose. | `FluxMonitor` Assets; the channel map and the dose computation carried pending. | The flux / dose-monitor modelling. |
| DIAG-1 | Nice-to-have | The Sydor beam-position monitor (per-quadrant currents, beam x / y, a sum-current total flux) and the position-versus-intensity split (the fleet-wide question). | A loose `BeamPositionMonitor` (held under review across 4-ID / 8-ID / 9-ID / ISS / FMX). | The beam-position-monitor catalog home. |
| READOUT-1 | Blocks-go-live | The offline mass-spectrometry readout: what artifact the beamline hands off (a footprinted aliquot in a fraction-collector tube? a capillary?), whether a sample-ID barcode is recorded, and where the dose record is the system of record. | The beamline produces a footprinted sample plus a dose record; the MS structural analysis is downstream, off the beamline. | The offline-readout seam. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the profile collection current and correct, and is the data plane Kafka plus Redis (no Tiled, no queue-server)? | The handles in the descriptor are taken from the profile collection and carried confirm; the data plane is the seam CORA's edge replaces. | Verifying each Asset's control handle and the data plane. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the front-end / photon shutters (only the front-end photon-shutter enable status is in the profile collection). | Permit leaves to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (the white-beam optics) and the cooling supply, plus the footprinting consumables (buffers, radical scavengers, the flow medium). | Photon beam, cooling water, and vacuum on the optics; the consumables as Supply. | The Supply observations. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure, and XFP's partner-beamline (Case Western) operating model. | Carried pending on the NSLS-II Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Does X-ray footprinting (the dose-delivery technique, with offline MS readout) enter CORA's catalog as a Capability / Method? | Deferred: carried as pending Practices; `x_ray_footprinting` is new, the fleet's first dose-delivery Method; not coined. | The technique Capability. |
