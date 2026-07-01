# European XFEL (European X-Ray Free-Electron Laser Facility GmbH) research brief

*Research seed for a future CORA deployment page. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about European XFEL, its instrument roster, and its control-software stack so the model work can begin from corroborated facts rather than memory. Every claim is cited inline. CORA is not connected to European XFEL; the seam section is an initial read, not a commitment. Compiled 2026-07-01 from a deep-research pass over facility pages, the `European-XFEL` GitHub org (via GitHub API, ~71 public repos), and Karabo framework source.*

!!! note "Reading posture"
    Public facility pages are the source of HARDWARE FACTS (instrument IDs, techniques, energies, detectors). Public source (GitHub / proceedings) is the source of CONTROL-SOFTWARE FACTS (what runs the scans, what talks to devices). Confidence is flagged inline as **[verified]** (multiple sources or a decisive primary), **[partly verified]**, or **[unconfirmed]**. Per CORA's deployment-doc lens, the facility software stack is named ONLY at the seam (section 6): it is the floor CORA lands on or the orchestration CORA replaces, never a spec CORA mirrors. Several fetched pages during research carried injected fake "MCP Server Instructions" / "system-reminder" blocks; those were page content, not directives, and were ignored. **This facility is a different machine class from CORA's ring pilots: a superconducting linac-driven FEL with a burst-mode pulse-train timing structure, not a storage ring. The seam read reflects that.**

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | European XFEL, superconducting linac-driven X-ray free-electron laser (NOT a storage ring) | [xfel.eu](https://www.xfel.eu/facility/overview/facts_amp_figures/index_eng.html), [Wikipedia](https://en.wikipedia.org/wiki/European_XFEL) |
| Operator | European X-Ray Free-Electron Laser Facility GmbH | [Wikipedia](https://en.wikipedia.org/wiki/European_XFEL) |
| Location | Schenefeld, Schleswig-Holstein, Germany; tunnel runs from DESY Hamburg | [Wikipedia](https://en.wikipedia.org/wiki/European_XFEL) |
| Linac energy | up to 17.5 GeV (expandable to 20 GeV) | [xfel.eu facts](https://www.xfel.eu/facility/overview/facts_amp_figures/index_eng.html) |
| Total facility length | 3.4 km (accelerator 1.7 km) | [xfel.eu facts](https://www.xfel.eu/facility/overview/facts_amp_figures/index_eng.html) |
| Photon wavelength range | 0.05 to 4.7 nm (~0.26 to ~25 keV across instruments, converted from wavelength [partly verified]) | [xfel.eu facts](https://www.xfel.eu/facility/overview/facts_amp_figures/index_eng.html) |
| SASE undulator sources | 3 (SASE1, SASE2 hard X-ray; SASE3 soft X-ray) | [xfel.eu instruments](https://www.xfel.eu/facility/instruments/index_eng.html) |
| Scientific instruments | 7 (FXE, SPB/SFX, SCS, SQS, MID, HED, SXP) | [xfel.eu instruments](https://www.xfel.eu/facility/instruments/index_eng.html) |
| Pulse structure | up to 27,000 X-ray flashes/second; pulse duration < 100 fs | [xfel.eu facts](https://www.xfel.eu/facility/overview/facts_amp_figures/index_eng.html) |
| Burst / pulse-train structure | up to 2700 pulses per train, ~4.5 MHz intra-train (220 ns spacing), 10 Hz train rate | [unconfirmed] widely-cited design figures; not pinned on a fetchable facility page |
| First light / operation | first lasing May 2017; inaugurated Sept 2017; instruments in user ops 2017-2019, SXP commissioning from 2022 | [xfel.eu instruments](https://www.xfel.eu/facility/instruments/index_eng.html), [Wikipedia](https://en.wikipedia.org/wiki/European_XFEL) |
| Control framework | Karabo SCADA framework (public, MPL-2.0 core / GPL-3.0 GUI) | [github.com/European-XFEL/Karabo](https://github.com/European-XFEL/Karabo) |

**[verified]** European XFEL is a superconducting-linac-driven hard-and-soft X-ray free-electron laser near Hamburg, delivering up to 27,000 X-ray flashes per second across three SASE sources feeding seven instruments. Its defining feature for any CORA read is the **burst-mode timing**: X-rays arrive in bunch trains (a dense ~4.5 MHz burst inside each train, trains repeating at 10 Hz [unconfirmed on the specific numbers]), not as a continuous top-up ring current. The single most citable hook for CORA's data-of-record / debrief value proposition is the **train-resolved data volume**: each instrument writes megahertz-rate detector data indexed by train ID and pulse, and the facility already runs a metadata catalog (myMdC) plus a heavy offline calibration pipeline, so the "system of record for the experiment" territory is actively contested here and worth understanding before any pitch.

---

## 2. Candidate beamlines

**Source-of-record posture (decides Tier-2 buildability): device topology is FIREWALLED.** The `European-XFEL` GitHub org publishes the **Karabo framework** and a large set of **device-integration classes** (cameras, detectors, SCPI instruments, EPICS/Tango mirrors), but a search of the org for per-instrument device configuration / project-database / topology repos returned nothing. The canonical device wiring lives on an **internal GitLab**: the public `euxfel_bunch_pattern` repo is labelled "mirror from EuXFEL Gitlab", and the Karabo/scan documentation on `rtd.xfel.eu` redirects to the auth-gated `in.xfel.eu`. So the per-instrument device list with real handles (Karabo device IDs, motor axes, PV/hardware bindings) is **not public**. This is a Sirius / PSI-style posture: **a Tier-2 device pass is NOT buildable from public source.** Device topology routes to the staff questions (section 7); it must not be inferred from the shared Karabo base classes (inference is not source).

What IS public and modellable: the **instrument roster** (below), the **control-framework shape** (Karabo, section 3), and the **data / calibration stack** (section 5). That is enough for a Tier-1 survey and a seam read, not for a candidate descriptor.

| Instrument | SASE source | Technique | Energy | Detectors | Control source | Source |
| --- | --- | --- | --- | --- | --- | --- |
| SPB/SFX | SASE1 | Single-particle imaging, serial femtosecond crystallography (SFX), time-resolved structure | 3-16 keV upstream, 6-16 keV downstream (up to 25 keV 3rd harmonic) | AGIPD 1 Mpx (upstream), AGIPD 4 Mpx (downstream) | Karabo; per-device config firewalled | [SPB/SFX](https://www.xfel.eu/facility/instruments/spb_sfx/index_eng.html) |
| FXE | SASE1 | Time-resolved XAS (XANES/EXAFS), XES/RIXS, XRD/WAXS/XDS | 4.6-22 keV | Jungfrau (2x 2D), Gotthard-2 (1D), LPD 1 Mpx, APDs | Karabo; per-device config firewalled | [FXE](https://www.xfel.eu/facility/instruments/fxe/index_eng.html) |
| MID | SASE2 | Coherent scattering/imaging: XPCS, CXDI, phase-contrast tomography, nanoscale dynamics | ~5-25 keV [partly verified] | AGIPD [partly verified] | Karabo; per-device config firewalled | [MID](https://www.xfel.eu/facility/instruments/mid/index_eng.html) |
| HED | SASE2 | High energy density / matter under extreme conditions; DAC, laser-shock (HIBEF UC: RE.LA.X + DiPOLE lasers) | ~5-25 keV [partly verified] | not stated on overview page [unconfirmed] | Karabo; per-device config firewalled | [HED](https://www.xfel.eu/facility/instruments/hed/index_eng.html) |
| SCS | SASE3 | Soft-X-ray spectroscopy + coherent scattering: XAS, RIXS (hRIXS), XRD, FFT/CHEM stations, ultrafast magnetism | soft X-ray (~0.25-3 keV) [partly verified] | DSSC | [SCS](https://www.xfel.eu/facility/instruments/scs/index_eng.html), [DSSCDevices](https://github.com/European-XFEL/DSSCDevices) |
| SQS | SASE3 | Small quantum systems: gas-phase AMO, non-linear/multi-photon, coherent scattering | 260-3000 eV | not stated on overview page [unconfirmed] | Karabo; per-device config firewalled | [SQS](https://www.xfel.eu/facility/instruments/sqs/index_eng.html), [Wikipedia](https://en.wikipedia.org/wiki/European_XFEL) |
| SXP | SASE3 | Time-resolved photoelectron spectroscopy at surfaces/interfaces | soft X-ray [partly verified] | not stated [unconfirmed] | Karabo; per-device config firewalled | [instruments](https://www.xfel.eu/facility/instruments/index_eng.html) |

**Strongest next picks given CORA's growth ladder (imaging/tomography-leaning):** the pilot ladder is APS 2-BM -> APS imaging -> MAX IV, and none of these seven instruments is a ring-style tomography station. The nearest technique adjacency for CORA's existing imaging/coherent-scattering model is **MID** (XPCS, CXDI, phase-contrast tomography) and **SPB/SFX** (diffractive imaging), with **FXE** the closest to the energy-scanning XAS/EXAFS lineage CORA has been chasing (the `energy_scan` Capability earn). But all three are **staff-question deployments**, not device passes: the topology is firewalled, and, more fundamentally, the burst-mode timing and megahertz detector data path make these a different modeling exercise from the ring pilots. European XFEL is best treated as a **candidate facility** (Tier-1 only) that stress-tests whether CORA's model generalizes to an FEL machine class, not as a near-term device-pass target.

**Identifier-scheme note:** European XFEL names by **instrument abbreviation** (FXE, SPB/SFX, SCS, SQS, MID, HED, SXP) bound to a **SASE source** (SASE1/2/3), not by `sector.station` (APS) or `I##/B##` (Diamond). Internally, Karabo addresses everything by hierarchical **device ID** (`INSTRUMENT/TYPE/NAME` style topic paths on the Karabo broker), and data is indexed by **proposal number + run number** with a per-pulse **train ID** timeline. The run-context identity CORA must map is therefore (proposal, run, train-ID range) over a Karabo device namespace, which differs from the EPICS-PV / BLISS-object handle model of the ring pilots. **[partly verified]** (device-ID scheme is Karabo-general; the exact per-instrument namespace is firewalled).

---

## 3. Control-system stack, by layer

The control system is **Karabo**, European XFEL's in-house SCADA framework, NOT EPICS or Tango as the primary substrate (though Karabo carries mirror devices to both). This is a third control-system family alongside the pilots' EPICS (APS/Diamond/NSLS-II) and BLISS/Tango (ESRF/MAX IV). **[verified]** ([Karabo repo](https://github.com/European-XFEL/Karabo), [karabo.eu](http://karabo.eu)).

### Device IO (the floor)

Karabo **device servers** host **devices** (C++ or Python), each exposing a schema of properties/commands; hardware is surfaced as Karabo devices. Public device-integration classes in the org show the floor's breadth: [`Karabo-aravisCameras`](https://github.com/European-XFEL/Karabo-aravisCameras) (GenICam/Aravis cameras), [`DSSCDevices`](https://github.com/European-XFEL/DSSCDevices) (DSSC soft-X-ray detector), [`Karabo-slsDetectors`](https://github.com/European-XFEL/Karabo-slsDetectors) (PSI SLS detectors, e.g. Jungfrau/Gotthard), [`Karabo-timepix3`](https://github.com/European-XFEL/Karabo-timepix3) + [`pytpx3`](https://github.com/European-XFEL/pytpx3) (ASI Timepix3), [`karabo-andorSdk3Cameras`](https://github.com/European-XFEL/karabo-andorSdk3Cameras) (Andor sCMOS), and [`scpiML`](https://github.com/European-XFEL/scpiML) + [`FunctionGenerator`](https://github.com/European-XFEL/FunctionGenerator) (SCPI instruments). Notably, Karabo integrates foreign control systems through **mirror devices**: [`Karabo-epicsMirror`](https://github.com/European-XFEL/Karabo-epicsMirror) and [`Karabo-tangoMirror`](https://github.com/European-XFEL/Karabo-tangoMirror). This is below CORA's seam; CORA would actuate through the Karabo device layer, never own it. **[verified]**

### Scan orchestration (the seam layer)

Karabo's high-level logic runs as **middlelayer devices** (Python), documented publicly at a framework level in [`howToMiddlelayer`](https://github.com/European-XFEL/howToMiddlelayer). Middlelayer devices coordinate other devices (async property access, state aggregation, proxies), which is the layer where a scan/alignment engine lives. **The specific scan tool** (whether a "scan" middlelayer device, a common-devices library, or a Karabacon-style scan environment) could not be confirmed from public source: the scan-tool documentation on `rtd.xfel.eu` redirects to the auth-gated `in.xfel.eu`, and no scan-orchestration repo is public in the org. This is the layer CORA's EdgeConductor would conduct over or replace, but its exact shape is a **staff question** (section 7). **[partly verified]** (middlelayer is the mechanism; the concrete scan device is firewalled).

### Fast paths and exceptions

The megahertz detector data path is a fast path distinct from Karabo property control: large-area detectors (AGIPD, LPD, DSSC, Jungfrau) stream **train-resolved** data through a dedicated DAQ ([`Karabo-DAQ`](https://github.com/European-XFEL/Karabo-DAQ), [`Karabo-Hdf5`](https://github.com/European-XFEL/Karabo-Hdf5), [`Karabo-DAQManagement`](https://github.com/European-XFEL/Karabo-DAQManagement)) rather than the standard property channel. Streaming to external consumers uses the **Karabo bridge** ([`karabo-bridge-py`](https://github.com/European-XFEL/karabo-bridge-py), ZeroMQ-based). Hardware timing/triggering is driven by the **bunch-pattern / train-ID** system ([`euxfel_bunch_pattern`](https://github.com/European-XFEL/euxfel_bunch_pattern), a mirror of internal GitLab) and a [`Karabo-UTIDServer`](https://github.com/European-XFEL/Karabo-UTIDServer) (universal timing ID provider). These widen any ControlPort surface well beyond simple motor/detector actuation and are FEL-specific. **[verified]** (repos exist and are described); exact wiring **[unconfirmed]**.

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| [`European-XFEL`](https://github.com/European-XFEL) (GitHub, ~71 public repos) | Karabo framework, device-integration classes, DAQ, data-analysis toolkit (EXtra*), calibration-adjacent tools | https://github.com/European-XFEL |
| Karabo on PyPI | `pip install karabo` (framework + middlelayer + GUI) | https://pypi.org/project/karabo/ |
| `git.xfel.eu` / EuXFEL internal GitLab | canonical per-instrument device config, deployment topology, project database | named in `euxfel_bunch_pattern` ("mirror from EuXFEL Gitlab"); DNS resolves (DESY net) but not public |
| `rtd.xfel.eu` -> `in.xfel.eu` | Karabo + scan-tool + data-analysis internal docs (auth-gated) | redirect observed 2026-07-01 |

**Why a full device model is NOT integrity-buildable from public source.** The Karabo framework and its device-integration classes are public, but they are **base classes and drivers, not instrument wiring**. The per-instrument device list (which devices are instantiated at SPB/SFX vs MID, their Karabo device IDs, motor axes, and hardware bindings) lives in the internal GitLab project database and is not published. Inferring instrument topology from the shared Karabo device classes would be exactly the fabrication this practice forbids. Device topology therefore routes to the staff questions (section 7), and no `beamline.candidate.yaml` is drafted for this facility.

---

## 5. Data management

European XFEL runs a mature, facility-wide data stack, and it is the **primary seam contest** here. **[verified]** on the public tooling; ingestion mechanics **[partly verified]**.

- **Format:** HDF5 in the EuXFEL run/proposal layout, indexed by **train ID** and pulse. Read via [`EXtra-data`](https://github.com/European-XFEL/EXtra-data) ("Access saved EuXFEL data", on PyPI as `extra_data`), with [`EXtra-geom`](https://github.com/European-XFEL/EXtra-geom) for detector geometry assembly and the broader [`EXtra`](https://github.com/European-XFEL/EXtra) toolkit. **[verified]**
- **Metadata catalog:** **myMdC** ("The Data Management portal for European XFEL users", at `in.xfel.eu/metadata`), login-gated with XFEL/DESY/CFEL campus credentials. This catalogs proposals/runs and drives the data lifecycle. It is a genuine "system of record" claimant over the CORA territory. **[verified]** it exists and is auth-gated; exact schema **[unconfirmed]**.
- **Calibration:** large-area detectors require an **offline calibration pipeline** (raw -> corrected) before science analysis; calibration constants are managed centrally. The public analysis docs point at the **Maxwell cluster** (DESY HPC) as where EXtra-data and calibrated data live (`module load exfel exfel-python`). The pipeline code itself (pycalibration / offline calibration) was not surfaced as a public repo in this pass. **[partly verified]**.
- **Live analysis / monitoring:** [`EXtra-foam`](https://github.com/European-XFEL/EXtra-foam) ("Fast Online Analysis Monitor"), [`DAMNIT`](https://github.com/European-XFEL/DAMNIT) + [`DAMNIT-web`](https://github.com/European-XFEL/DAMNIT-web) ("automated experiment overview") for per-run inspection, and [`pasha`](https://github.com/European-XFEL/pasha) for shared-memory parallel processing. DAMNIT in particular is a run-debrief/overview surface CORA's RunDebriefer would contend with. **[verified]**.
- **Proposal API:** [`extra-proposal`](https://github.com/European-XFEL/extra-proposal) ("a high-level proposal API") exposes proposal/run structure programmatically. **[verified]**.

The ingestion trigger (is myMdC cataloging mandatory, and at what point in a run) and whether calibrated data or raw is the durable record are **staff questions**.

---

## 6. The CORA seam (initial read)

First pass, not a committed seam. Applies the 2-BM / FXI lens, adjusted for the FEL machine class: **the machine class changes the seam more than at any ring pilot.** European XFEL is not a storage ring; the timing substrate (bunch trains, train IDs, 27,000 flashes/s) and the megahertz detector data path are structurally different from CORA's ring model, where a run is a sequence of exposures at a top-up-stable current.

**Where the floor stays the floor (drive through, never CORA).** The Karabo **device layer** is the floor: device servers surfacing cameras, detectors, motors, and SCPI/EPICS/Tango-mirror devices. CORA never owns Karabo devices. But the APS-pilot **ControlPort model does NOT carry over unchanged**: the pilots' ControlPort actuates EPICS PVs (and, at ESRF/MAX IV, BLISS/Tango objects); here it would actuate **Karabo devices** over the Karabo broker, a third adapter target. A `KaraboControlPort` adapter would be new work, and the bunch-pattern / train-ID timing means the "acquire an exposure" primitive is really "arm for a train and collect a pulse-resolved burst", which the ring-oriented Actuate axis does not model today.

**What CORA replaces (edge orchestration).** The scan/alignment logic implemented as Karabo **middlelayer devices** (the scan tool, exact name firewalled). CORA's EdgeConductor would conduct routines over the Karabo floor where those middlelayer scan devices sit today, incrementally and routine-by-routine. Karabo is a solid, mature in-house SCADA system; treat it as DATA to learn from (device model, train-synchronous coordination), NOT a spec to mirror, and pitch CORA on governance, replayability, and recipe-binding, never on out-executing Karabo's megahertz DAQ on speed. The FEL replace-vs-drive-through call is heavier than at a ring because the timing/DAQ coupling is tight.

**Source-of-truth contest (data).** This is the sharpest contest in the fleet so far. **myMdC** (metadata catalog), the **EXtra-data** run store on Maxwell, the **calibration pipeline**, and **DAMNIT** (automated experiment overview / debrief) together already occupy much of the "system of record for the experiment" and "debrief" territory CORA claims. CORA stays the system of record for the *experiment governance and provenance spine* (which none of these carry as an event-sourced whole), and names myMdC/EXtra-data only at the seam, either fed downstream or projected into. The decision defers until a European XFEL deployment is actually in scope, but the contest should be understood as **active and well-developed here**, unlike the thinner catalog stories at some ring pilots.

**Coexist.** Proposal/scheduling/identity (myMdC + the proposal API, read not replaced); offline calibration + reconstruction compute on Maxwell (a port roundtrip CORA governs but does not own); the tape/Maxwell archive (an egress destination); DAMNIT-style overview (subsumed at CORA's debrief layer, where CORA's RunDebriefer already exists as a present strength, not a someday).

---

## 7. Open questions (for facility staff)

These could not be settled from public sources and need operator confirmation before any seam lock.

1. **ControlPort surface (Karabo):** what is the concrete actuation boundary CORA would drive, a Karabo middlelayer proxy, the C++/Python device API, or the Karabo broker directly? What broker does Karabo use (JMS/OpenMQ vs AMQP/RabbitMQ vs Redis) and does that matter for a `KaraboControlPort` adapter?
2. **Scan orchestration:** what is the actual scan/alignment engine, is there a named scan tool (Karabacon-style) or a common-devices library, and which routines are middlelayer-device-implemented vs operator-driven? This bounds what EdgeConductor would replace.
3. **Per-instrument device topology (firewalled):** the Karabo device inventory per instrument (device IDs, motor axes, detector bindings) that lives on the internal `git.xfel.eu` GitLab. Without this, no device pass is buildable.
4. **Burst-mode timing:** confirm the pulse-train parameters (pulses per train, intra-train MHz spacing, train repetition rate) and how a "run" and an "acquisition" map onto trains and train-ID ranges, so CORA's run/exposure model can be reconciled with the FEL timing substrate.
5. **Data catalog seam (myMdC):** is cataloging mandatory, at what point in a run does ingestion fire, and is raw or calibrated data the durable record? Where does CORA's provenance spine sit relative to myMdC + EXtra-data on Maxwell?
6. **Calibration pipeline:** is offline calibration (raw -> corrected) inline with or downstream of acquisition, is the pipeline code (pycalibration / offline calibration) reachable, and does CORA govern the calibration roundtrip as a compute port?
7. **Identity / governance:** the proposal/user-office model (User Portal / UPEX), the role/permission model, and the safety/PSS layer, for mapping CORA's Trust BC. Which map onto Karabo devices vs a separate safety system?

---

## 8. Source list

**Facility (hardware facts):**
- European XFEL instruments: https://www.xfel.eu/facility/instruments/index_eng.html
- Facts and figures: https://www.xfel.eu/facility/overview/facts_amp_figures/index_eng.html
- SPB/SFX: https://www.xfel.eu/facility/instruments/spb_sfx/index_eng.html
- FXE: https://www.xfel.eu/facility/instruments/fxe/index_eng.html
- MID: https://www.xfel.eu/facility/instruments/mid/index_eng.html
- HED: https://www.xfel.eu/facility/instruments/hed/index_eng.html
- SCS: https://www.xfel.eu/facility/instruments/scs/index_eng.html
- SQS: https://www.xfel.eu/facility/instruments/sqs/index_eng.html
- Wikipedia, European XFEL: https://en.wikipedia.org/wiki/European_XFEL
- DESY photon science, European XFEL: https://photon-science.desy.de/facilities/european_xfel/index_eng.html

**Control system (software facts):**
- European-XFEL GitHub org: https://github.com/European-XFEL
- Karabo SCADA framework: https://github.com/European-XFEL/Karabo (http://karabo.eu, PyPI https://pypi.org/project/karabo/)
- howToMiddlelayer (Karabo middlelayer docs): https://github.com/European-XFEL/howToMiddlelayer
- Karabo-DAQ: https://github.com/European-XFEL/Karabo-DAQ
- Karabo-Hdf5: https://github.com/European-XFEL/Karabo-Hdf5
- Karabo-DAQManagement: https://github.com/European-XFEL/Karabo-DAQManagement
- karabo-bridge-py: https://github.com/European-XFEL/karabo-bridge-py
- Karabo-epicsMirror: https://github.com/European-XFEL/Karabo-epicsMirror
- Karabo-tangoMirror: https://github.com/European-XFEL/Karabo-tangoMirror
- Karabo-aravisCameras: https://github.com/European-XFEL/Karabo-aravisCameras
- DSSCDevices: https://github.com/European-XFEL/DSSCDevices
- Karabo-slsDetectors: https://github.com/European-XFEL/Karabo-slsDetectors
- Karabo-timepix3: https://github.com/European-XFEL/Karabo-timepix3
- karabo-andorSdk3Cameras: https://github.com/European-XFEL/karabo-andorSdk3Cameras
- scpiML: https://github.com/European-XFEL/scpiML
- Karabo-UTIDServer: https://github.com/European-XFEL/Karabo-UTIDServer
- euxfel_bunch_pattern (mirror from internal GitLab): https://github.com/European-XFEL/euxfel_bunch_pattern

**Data management:**
- EXtra-data: https://github.com/European-XFEL/EXtra-data (docs https://extra-data.readthedocs.io/, PyPI extra_data)
- EXtra-geom: https://github.com/European-XFEL/EXtra-geom
- EXtra (toolkit): https://github.com/European-XFEL/EXtra
- extra-proposal: https://github.com/European-XFEL/extra-proposal
- EXtra-foam (online analysis monitor): https://github.com/European-XFEL/EXtra-foam
- DAMNIT / DAMNIT-web: https://github.com/European-XFEL/DAMNIT , https://github.com/European-XFEL/DAMNIT-web
- pasha: https://github.com/European-XFEL/pasha
- myMdC metadata catalog (login-gated): https://in.xfel.eu/metadata

**Internal-only (named, not reachable):** `git.xfel.eu` (EuXFEL internal GitLab, canonical device config), `in.xfel.eu` / `rtd.xfel.eu` (auth-gated Karabo + scan-tool + data-analysis docs), Maxwell cluster (DESY HPC, EXtra-data + calibrated data host).
