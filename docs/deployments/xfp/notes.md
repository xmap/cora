# Notes

## Techniques

*What the modelled part of XFP is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md#the-techniques-adapted-here) is how a facility adapts it. XFP does one technique, **X-ray footprinting**, in two delivery modes: static / capillary-flow, and shutterless high-throughput. The Method below renders unlinked and is carried pending until the owner-scope decision (`TECH-1`) brings it into the catalog.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray footprinting (capillary-flow / static) | `x_ray_footprinting` | gate a timed white-beam dose onto a flowing solution capillary or flow-cell sample, recording exposure time x flux x attenuation as the delivered dose; the fleet's first dose-delivery Method, new to the catalog; readout is offline mass spec (`TECH-1`, `READOUT-1`) |
| High-throughput footprinting (HTFly) | `x_ray_footprinting` | sweep a fly-cell row through the defining slit at a set stage velocity so the exposure (dose) is the slit gap over the velocity, across a 96-well plate; the same `x_ray_footprinting` Method with the HTFly stage as the dose-timing (`TECH-1`, `HT-1`) |

Both modes need the [white-beam chain](source.md) (the mirror, the slits, the Al filter wheel for dose rate), the [dose gating](source.md) (the timed shutters or the delay-generator-fired Uniblitz, or the HTFly velocity), the [sample side](sample.md) (a stage and the delivery pump), and the [flux monitors](detector.md) (to record the delivered dose). They differ only in how the exposure is timed and how many samples are handled.

### The technique is dose delivery, and the readout is offline

This is the heart of what makes XFP a new shape for CORA. X-ray footprinting is not a measurement technique in the sense the rest of the fleet uses: the beamline does not record a structural signal. It **delivers a controlled radiolytic dose** to a biological macromolecule in solution, generating hydroxyl radicals that covalently modify the molecule at solvent-accessible sites. The modified sample is then analysed **offline by mass spectrometry**, which reveals which residues were exposed and thus maps the molecule's surface and conformational changes.

So the Method `x_ray_footprinting` is a **dose-delivery** Method:

- its controlled variable is the delivered dose (exposure time times flux times attenuation), not a detector setting;
- its product is a footprinted sample plus a dose record, not a measurement frame;
- its structural readout is the offline-readout seam (mass spec, downstream and off the beamline, `READOUT-1`).

That is why `x_ray_footprinting` is proposed as a Method distinct from anything in the catalog: not because the optics are unusual (a white beam, a filter, a shutter), but because the experiment shape, dose-in, sample-out, structure-read-elsewhere, is genuinely new. Whether the catalog ultimately holds a `x_ray_footprinting` Capability, or a broader "controlled-dose / irradiation" Capability with footprinting as a Practice adaptation, is the owner-scope decision (`TECH-1`); XFP records the case, it does not mint the vocabulary. The matching Site Practices (`XFP_footprinting_practice`, `XFP_high_throughput_footprinting_practice`) are carried pending in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here); each binding lands when its Capability does.

### A time-resolved mode, deferred

The profile collection also contains a time-resolved capillary-flow mode (a stopped-flow style mixing experiment before irradiation), but it is flagged unfinished in the source, so no Practice is recorded for it here; it is a later mode that would reuse the same `x_ray_footprinting` Method with a mixing step in the Procedure (`TECH-1`).

### Not modelled yet

The concrete acquisition recipes are not written yet. For footprinting that is the dose series (the set of exposure times or filter thicknesses that build a dose-response curve), the flow program that presents fresh sample, the aliquot-collection pattern, and the flux-to-absorbed-dose calibration that converts the measured flux to the dose the sample received (a seam constant that lives in offline analysis, `DOSE-1`). The downstream linkage to the offline mass-spec result is the offline-readout seam, not a beamline recipe (`READOUT-1`). These join as the deployment approaches the point where CORA drives XFP.

Whether `x_ray_footprinting` enters CORA's catalog is an owner-scope decision on [Model](#model): a modelling exercise reinforces the case but does not mint cross-facility Method vocabulary on its own. See [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at XFP, and the trust shape that will gate it. First cut.*

Governance at XFP follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

XFP is not yet driven by CORA, so this shape is not yet instantiated. As a modelling-exercise scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. XFP is a Case Western Reserve University partner beamline operated within NSLS-II, so its operator and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md#safety-and-governance), with the partner-beamline operating model itself an open question (`GOV-1`).

### The safety boundary

The safety tier is the other piece that is not yet settled. Only the front-end photon-shutter enable status is in the beamline's profile collection (interlock-derived; plans refuse to open the shutter when it is disabled), so the Enclosure permit leaves and the rest of the search-and-secure structure are carried pending and not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

XFP brings two distinctive hazards: a high-flux white beam, and the dose it delivers. They land with the equipment and the experiment that bring them, and an experiment Clearance would carry them.

| Hazard class | Where it lands | Tracking |
| --- | --- | --- |
| High-flux white / pink X-ray beam | the [optics](index.md) and [endstation](index.md) enclosures (FE:C17B, XF:17BM / XF:17BMA) (`ENC-1`) | (`PSS-1`, `WHITE-1`) |
| Delivered radiolytic dose to biological samples | the [dose-delivery gating](source.md) and the [Sample](sample.md) side | (`DOSE-1`, `SUBJECT-1`) |
| Vacuum white-beam optics | the [Source](source.md) walk | (`SUP-1`) |
| Biological samples, buffers, and fluidics | the [Sample](sample.md) delivery chain | (`FLOW-1`, `SUBJECT-1`) |

The high-flux white beam is the interlocked hazard; its permit leaves stay pending until the PSS signals are confirmed (`PSS-1`). The delivered dose is itself a controlled hazard at a footprinting beamline, distinctive to its dose-delivery character, and travels with the dose-gating chain and the Subject (`DOSE-1`, `SUBJECT-1`). The biological-sample and fluidics hazards travel with the delivery chain (`FLOW-1`). None of these is invented; each is carried against its question.

### When the shape lands

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives XFP, following the [2-BM governance](../2-bm/governance.md) shape. Because XFP shares the NSLS-II EPICS and ophyd floor with the rest of the fleet, it re-tests the Site and Federation kernel rather than introducing a new trust model. The distinctive wrinkles are the partner-beamline operating model (`GOV-1`) and the offline-readout seam: a Conduit would bound the dose-delivery command surfaces, while the downstream mass-spec analysis sits outside the beamline's trust boundary entirely (`READOUT-1`). The Zone groups the same optics and endstation resources the [inventory](index.md) lists; the Policies bind to the NSLS-II operator roles carried pending at the Site (`GOV-1`).

## Model

*The developer's by-kind index: where each CORA aggregate's XFP content lives, how it models a beamline with no detector and an offline readout, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at XFP |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes XFP new

XFP is the most structurally distinct deployment in the fleet. Every other beamline CORA models is a measurement beamline: condition a beam, place a sample, record a detector signal. XFP is a **dose-delivery** beamline with **no detector**. Its contributions:

- **Dose as the experiment variable.** The controlled quantity is the delivered radiolytic dose (exposure time times incident flux times attenuation), not a detector setting. The whole apparatus, the timed shutters, the delay-generator-fired millisecond fast shutter, the Al filter wheel, and the flux monitors, exists to set and measure that dose.
- **A sample-and-record output, not frames.** A footprinting run produces a footprinted sample (an irradiated aliquot) plus a dose record (exposure time, filter thickness, flux time-series, well / tube identity). There are no measurement frames.
- **The offline-readout seam.** The structural readout (which residues were modified) is offline mass spectrometry, downstream and off the beamline. CORA is the system of record for the dose and the sample provenance; the MS analysis is a separate, later step.
- **A solution Subject.** Like LIX, the specimen is a biological macromolecule in a buffer, delivered fluidically.

### No new families

XFP coins no new Family and changes nothing in the catalog. The whole device tree reuses existing vocabulary; the novelty is in the Method, the Subject, and the seam, not in device classes.

- **17-BM is a bending-magnet, white / pink beam source** (no insertion device, no monochromator in the footprinting path); machine state is observed through the loose `StorageRing`, and the white-versus-mono scope is `SRC-1` / `WHITE-1`.
- **The dose chain reuses the catalog:** the bendable mirror binds `Mirror`; the slits bind `Slit`; the Al filter wheel binds `Filter` (it sets the dose rate); the timed shutters bind `Shutter`; the delay generator that fires the millisecond Uniblitz fast shutter binds `TimingController` (its opening-time setpoint is the dose time); the QuadEM electrometers bind `FluxMonitor`; the Sydor beam-position monitor binds the graduated catalog `PositionMonitor` (presenting `Sensor`, distinct from `FluxMonitor` by measuring beam position rather than flux; per-Asset channel map open, `DIAG-1`); the sample stages bind `LinearStage`.

### How a beamline with no detector is modelled

XFP has no Detector-role imaging device, and CORA models that honestly rather than inventing one:

- the detection side holds **flux / dose monitors** (`FluxMonitor`, the graduated catalog `PositionMonitor`), which measure the delivered dose, not a sample signal;
- the dose-delivery role is expressed by the **Source gating** (Shutter + `TimingController` + `Filter`) plus those flux monitors, not by a detector;
- the structural readout is the **offline-readout seam**: the run's product is a footprinted sample plus a dose record, and the mass-spec analysis happens downstream, off the beamline (`READOUT-1`).

This is the deliberate inversion: where a measurement beamline's run is anchored on a Dataset of detector frames, an XFP run is anchored on a dose record and a Subject (the footprinted aliquot), with the structural Dataset produced elsewhere and linked back later.

### The FlowController rule-of-three

The one device reuse worth naming is the sample-delivery pump. Its anatomy is a settable flow / pump actuator (rate / volume setpoints, a run command), exactly the catalog `FlowController` Family that i22, 7-BM, and LIX already use. So the pump **reuses** `FlowController`; it coins nothing. XFP is its **fourth** consumer (i22, 7-BM, LIX, XFP), and `FlowController` has now **graduated** into the catalog on this rule-of-three: it presents the existing `Regulator` Role (the settable-actuator sibling of `TemperatureController`), earned across i22 / 7-BM / LIX / XFP, like `EmissionSpectrometer` and `TemperatureController` before it. The wider fluidic chain beyond the pump (selector valves, SEC columns, flow cells, fraction collectors) stays in the `ControlPort` seam pending its own rule-of-three (`FLUID-1`).

### Deliberately not here yet

- **The fraction collector Family (`FC-1`).** The fraction collector is a PV-bound aliquot-routing actuator with no clean existing Family. At n=1 CORA does not coin a `FractionCollector` Family; it is carried in the sample-custody seam (the footprinted-sample hand-off to offline MS).
- **The 96-well plate handler (`HT-1`).** The plate is addressed in pure Python (8 columns x 12 rows, a coordinate table, no robot and no PV); it is a Procedure over the spine plus a Subject custody thread, the i03 / MX3 / LIX custody-as-Procedure precedent (XFP at the no-robot end of that spectrum), not a device Family.
- **The offline mass-spec readout (`READOUT-1`).** The structural analysis is downstream, off the beamline, and absent from the profile collection. A future integration could link the offline MS result back to the dose record; it is not modelled here.
- **The Method.** Whether `x_ray_footprinting` (or a broader controlled-dose / irradiation Capability) enters CORA's catalog is an owner decision; the Practices render unlinked, pending (`TECH-1`).
- **The intermittently-connected and out-of-scope hardware.** The 0-9 mm Al z-attenuator, the beam-defining pinhole stages, the greenfield Galil stages, and the temperature / bias diagnostics are intermittently connected or read-only and not modelled as core devices (`ATTN-1`, `TEMP-1`); the monochromatic XAS endstation (ES:3) is a separate endstation, out of scope for footprinting (`WHITE-1`).
- **The time-resolved mixing mode.** The stopped-flow time-resolved footprinting mode is flagged unfinished in the source; no Practice is recorded for it (`TECH-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_xfp_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the XFP team to confirm before the model can be trusted.*

XFP was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/xfp-profile-collection](https://github.com/NSLS2/xfp-profile-collection)), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from the `startup/` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are the optics (FE:C17B, XF:17BM-OP / XF:17BMA-OP) and the endstations (XF:17BMA-ES:1, ES:2) separate hutches? | Two enclosures: a `xfp-optics` zone and the `xfp-endstation` hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The 17-BM source (a bending magnet is implied by the name and the white-beam design; the profile collection exposes no source device, only ring current). | A bending-magnet source, observed only through the machine state. | The source Asset detail. |
| WHITE-1 | Blocks-go-live | Is routine footprinting white beam or pink beam (filtered by the mirror cutoff and the Al filters), and is there any monochromator in the footprinting path? (A DCM exists only on a separate XAS endstation, ES:3, excluded here.) | White / pink beam, no monochromator in the footprinting path; ES:3 out of scope. | The beam-conditioning model. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state XFP reads (only the ring current is read for a beam-present suspender). | Observe-only machine state, a loose `StorageRing`; the rest pending. | The machine-state observation. |
| OPT-1 | Nice-to-have | The front-end mirror coating and bend mechanism (a bendable mirror with a Bend focus axis and thermocouples). | A bendable focusing `Mirror`; coating and bend pending. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The blade-axis roles of the white-beam, PB / PDS, and ADC defining slits (the ADC horizontal gap sets the HTFly exposure window). | Four-blade / center-gap slits bound to `Slit`. | The slit Asset detail. |
| ATTN-1 | Blocks-go-live | The attenuation chain that sets the dose RATE: the eight-position Al filter wheel, plus the intermittently-connected 0-9 mm Al z-attenuator and the beam-defining pinhole apertures. | The filter wheel binds `Filter`; the pinhole / z-attenuator are further attenuators carried pending. | The dose-rate attenuator modelling. |

### Dose delivery

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DOSE-1 | Blocks-go-live | The dose-delivery chain: the timed shutters (the EPS pre-shutter, the PPS photon shutter, the inner DIODE sample shutter), the DG535 delay generator that fires the millisecond Uniblitz fast shutter (its opening-time setpoint is the dose time), and the flux-to-absorbed-dose calibration (which lives in offline analysis). | Seconds-scale dose is software-timed on the pre-shutter (`Shutter`); millisecond dose is the delay-generator-fired Uniblitz (`TimingController`); the dose calibration is offline. | The dose-delivery modelling. |

### Sample and delivery

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The capillary-flow sample stage axes and how a flowing solution capillary mounts in the beam. | A `LinearStage` for the capillary-flow stage; the flow is the fluidic seam. | The sample-stage modelling. |
| HT-1 | Blocks-go-live | The high-throughput modes: the 96-well plate stage and addressing (8 columns x 12 rows, addressed in pure Python with a coordinate table, no robot and no PV), and the shutterless HTFly stage (exposure = defining-slit gap over stage velocity). | `LinearStage` stages; the well addressing and the HTFly dose-timing are Procedures over the spine plus a Subject custody thread. | The high-throughput modelling. |
| FLOW-1 | Nice-to-have | The sample-delivery pumps (an M50 pump and a PHD2000 infusion pump, both with rate / volume setpoints), which units are live, and the per-Asset pump detail. | The pump binds the graduated catalog `FlowController` (presents Regulator; earned on the i22 / 7-BM / LIX / XFP rule-of-three); the wider fluidic chain stays in the seam (`FLUID-1`). | The pump modelling; the CORA decision is on [Model](#deliberately-not-here-yet). |
| FC-1 | Nice-to-have | The fraction collector (a PV-bound aliquot-routing actuator: a collect / waste valve, a tube index, a fill pattern) that captures footprinted aliquots, and whether it earns a Family. | Carried in the sample-custody seam (the footprinted-sample hand-off to offline MS); no `FractionCollector` Family coined at n=1. | The fraction-collector modelling. |
| SUBJECT-1 | Nice-to-have | The solution Subject: a biological macromolecule (protein / nucleic acid) in a buffer, irradiated, with its own provenance. | A liquid Subject; the footprinted aliquot is the run's output, carried to offline MS. | The Subject modelling. |
| TEMP-1 | Nice-to-have | The temperature / bias diagnostics (the SR630 thermocouple monitor and the Sydor bias / thermocouple controller), used as alignment-flux proxies. | Read-only diagnostics, not core footprinting devices; deferred. | The temperature-diagnostic modelling. |

### Detection and readout

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The flux / dose monitors: the QuadEM electrometers (incident flux plus a per-exposure time-series), the DIODE PDM array-logger, and which channels measure the delivered dose. | `FluxMonitor` Assets; the channel map and the dose computation carried pending. | The flux / dose-monitor modelling. |
| DIAG-1 | Nice-to-have | The Sydor beam-position monitor (per-quadrant currents, beam x / y, a sum-current total flux) and the per-Asset position-versus-intensity split. The `PositionMonitor` Family itself is settled (graduated catalog Family presenting `Sensor`). | A graduated catalog `PositionMonitor` (earned across the wide fleet that shares it); only the per-Asset channel map is pending. | The beam-position-monitor channel map. |
| READOUT-1 | Blocks-go-live | The offline mass-spectrometry readout: what artifact the beamline hands off (a footprinted aliquot in a fraction-collector tube? a capillary?), whether a sample-ID barcode is recorded, and where the dose record is the system of record. | The beamline produces a footprinted sample plus a dose record; the MS structural analysis is downstream, off the beamline. | The offline-readout seam. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the profile collection current and correct, and is the data plane Kafka plus Redis (no Tiled, no queue-server)? | The handles in the descriptor are taken from the profile collection and carried confirm; the data plane is the seam CORA's edge replaces. | Verifying each Asset's control handle and the data plane. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the front-end / photon shutters (only the front-end photon-shutter enable status is in the profile collection). | Permit leaves to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (the white-beam optics) and the cooling supply, plus the footprinting consumables (buffers, radical scavengers, the flow medium). | Photon beam, cooling water, and vacuum on the optics; the consumables as Supply. | The Supply observations. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure, and XFP's partner-beamline (Case Western) operating model. | Carried pending on the NSLS-II Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Does X-ray footprinting (the dose-delivery technique, with offline MS readout) enter CORA's catalog as a Capability / Method? | Deferred: carried as pending Practices; `x_ray_footprinting` is new, the fleet's first dose-delivery Method; not coined. | The technique Capability. |
