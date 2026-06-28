# XFP

*The X-ray Footprinting beamline at NSLS-II, beamline 17-BM (a Case Western Reserve University partner beamline): synchrotron X-ray footprinting of biological macromolecules in solution. An intense white / pink beam generates hydroxyl radicals that covalently modify a protein or nucleic acid at solvent-accessible sites; the structural readout is done offline by mass spectrometry. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `XFP` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 17` (PV namespace `XF:17BM*`; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (descriptor + docs; scenarios deferred) |
| Source | A bending magnet, white / pink beam, no monochromator in the footprinting path (`SRC-1`, `WHITE-1`) |
| Control stack | NSLS-II EPICS / ophyd, Kafka + Redis data plane (no Tiled, no queue-server); handles bound from the profile collection, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/xfp-profile-collection](https://github.com/NSLS2/xfp-profile-collection)). EPICS PVs are real and read from the `startup/` files; vendor part numbers, serials, dose calibrations, and physical positions are not in the profile collection and are open questions. Every value is carried as `confirm` until XFP staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes XFP different

XFP is the most structurally different beamline in the fleet, so read this carefully. Every other deployment CORA models is a **measurement** beamline: it conditions a beam, puts a sample in it, and a detector records a signal (a scattering pattern, a diffraction image, a spectrum, a tomogram). XFP is a **dose-delivery** beamline. It has **no scattering, area, or imaging detector at all**. Its job is to deliver a controlled radiolytic **dose** to a biological sample in solution; the actual structural readout, which residues were modified, is done **offline by mass spectrometry**, downstream and off the instrument.

That inverts the usual shape, and it is what makes XFP worth modelling:

- **The experiment variable is dose, not a measured signal.** Delivered dose is exposure time times incident flux times attenuation. The beamline's whole apparatus, the timed shutters, the delay-generator-fired millisecond fast shutter, the Al filter wheel, and the flux monitors, exists to set and measure that dose (`DOSE-1`).
- **The run produces a sample and a record, not frames.** A footprinting run produces (a) a footprinted **sample**, an irradiated aliquot, often captured into a fraction-collector tube, and (b) a **dose record**: exposure time, filter thickness, the flux time-series, and the well or tube identity. There are no measurement frames to store (`READOUT-1`).
- **The structural readout is the offline-readout seam.** The mass spectrometry that turns a footprinted sample into a structural map is downstream, off the beamline, and absent from the profile collection. CORA's run is the system of record for the dose and the sample provenance; the MS analysis is a separate, later step (`READOUT-1`).
- **The Subject is a biomolecule in solution.** Like [LIX](../lix/index.md), the specimen is a protein or nucleic acid in a buffer, delivered by a fluidic chain, not a solid mount (`SUBJECT-1`).

XFP coins **no new Family**. The whole device tree reuses existing vocabulary; the novelty lands on the Method (radiolytic footprinting), the Subject, and the offline-readout seam, not on device classes. The one reuse worth naming is the sample-delivery pump, which binds the catalog `FlowController` Family (graduated; presents Regulator), with XFP its fourth consumer (see below).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics (`FE:C17B`, `XF:17BM-OP`, `XF:17BMA-OP`) | Yes | The bendable front-end mirror, the white-beam and defining slits, the Al filter wheel (`ENC-1`, `WHITE-1`) |
| Dose-delivery gating | Yes | The personnel and timed dose shutters, the delay generator that fires the millisecond Uniblitz fast shutter (`DOSE-1`) |
| Endstation (`XF:17BMA-ES:1`, `ES:2`) | Yes | The capillary-flow, high-throughput, and HTFly sample stages, the delivery pump, the flux and beam-position monitors (`ENC-1`) |
| New device classes | None | Zero new Families coined by XFP; the delivery pump reuses the graduated catalog `FlowController` |
| The sample-delivery pump | Catalog `FlowController` (graduated; presents Regulator) | Reuses the flow / pump-actuator Family (i22 / 7-BM / LIX); XFP is its fourth consumer, the rule-of-three FlowController graduated on (`FLOW-1`) |
| Any scattering / area / imaging detector | No (does not exist) | XFP is dose-delivery; the readout is offline MS, so the detection side is flux / dose monitors only (`READOUT-1`, `DET-1`) |
| The fraction collector + 96-well plate | Seam + Subject / Procedure | The aliquot-routing collector and the pure-Python well addressing are the sample-custody seam, not devices (`FC-1`, `HT-1`) |
| The monochromatic XAS endstation (`ES:3`) | No (out of scope) | A separate endstation; footprinting is white / pink beam (`WHITE-1`) |
| Integration scenarios + vendor Models | No | Design-phase; the descriptor and docs come first |

The deferred parts are recorded on [Model](model.md).

## Key modelling decisions

- **XFP is a dose-delivery beamline with no Detector-role device.** The detection side models flux / dose monitors (`FluxMonitor`, loose `BeamPositionMonitor`) and the offline-readout seam, not an imaging detector (`READOUT-1`, `DET-1`).
- **17-BM is a bending-magnet, white / pink beam source.** There is no insertion device and no monochromator in the footprinting path; machine state is observed through the loose `StorageRing`, and the white-versus-mono scope is carried pending (`SRC-1`, `WHITE-1`).
- **The dose chain reuses the catalog.** The Al filter wheel binds `Filter` (it sets the dose rate); the timed shutters bind `Shutter`; the delay generator that fires the millisecond Uniblitz fast shutter binds `TimingController` (its opening-time setpoint is the dose time); the QuadEM electrometers bind `FluxMonitor` (incident flux to compute dose) (`DOSE-1`).
- **The sample-delivery pump reuses the graduated catalog `FlowController`.** XFP is its **fourth** consumer (i22, 7-BM, LIX, XFP); `FlowController` graduated on this rule-of-three, presenting the `Regulator` Role (the settable-actuator sibling of `TemperatureController`). The wider fluidic chain beyond the pump stays in the `ControlPort` seam (`FLUID-1`).
- **The fraction collector, the 96-well plate, and the offline MS are the sample-custody and offline-readout seam.** The aliquot-routing fraction collector has no clean Family at n=1 and is carried in the custody seam; the 96-well plate is addressed in pure Python (no robot, no PV) as a Procedure plus a Subject custody thread, the i03 / MX3 / LIX custody-as-Procedure precedent (XFP at the no-robot end); the mass-spec readout is downstream and off the beamline (`FC-1`, `HT-1`, `READOUT-1`, `SUBJECT-1`).
- **Zero new Families coined by XFP; its delivery-pump sighting is the fourth that graduated the catalog `FlowController` Family (presents Regulator).**

## The beamline

- [Source](beamline.md): the generated device walk: the storage-ring machine state, the bendable front-end mirror, the white-beam and defining slits, the Al filter wheel, and the dose-delivery gating (the personnel and timed shutters, the delay-generator dose timer).
- [Sample](equipment/sample.md): the capillary-flow, high-throughput, and HTFly sample stages, the sample-delivery pump, and where the fraction collector, the 96-well plate, and the solution Subject sit.
- [Detector](equipment/detector.md): the flux and beam-position monitors that measure the delivered dose, and why there is no imaging detector (the offline mass-spec readout).

Cutting across them:

- [Controls](equipment/controls.md): the EPICS / ophyd control stack, the dose-delivery timing, the sample-custody seam, and the offline-readout seam; handles bound from the profile collection and carried confirm (`CTRL-1`).

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/xfp/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of XFP is designed to do, as intent. X-ray footprinting (static / capillary-flow and shutterless high-throughput) maps to a new `x_ray_footprinting` Method, the fleet's first dose-delivery Method. It renders unlinked, carried pending (`TECH-1`).

## Governance

[Governance](governance.md): who will act at XFP and the trust shape that gates their commands. People and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here), surfacing through their actions and gated by a Zone-plus-Conduit-plus-Policy trust shape. The NSLS-II operator pool and review are pending at the Site (`GOV-1`); only the front-end photon-shutter enable status is in the profile collection, so the rest of the PSS signals are carried pending, not invented (`PSS-1`).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's XFP content lives, and the record of what is deliberately deferred. XFP introduces no new Family.

## Not yet documented

XFP is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS search-and-secure permit signals and the offline mass-spec readout integration are not invented here (`PSS-1`, `READOUT-1`).
