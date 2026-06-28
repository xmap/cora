# PSI / SLS TOMCAT (S-TOMCAT + I-TOMCAT) research brief

*Research seed for a future CORA deployment page. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about the PSI Swiss Light Source tomography lineage and its control-software stack so the model work can begin from corroborated facts rather than memory. Every claim is cited inline. CORA is not connected to TOMCAT; the seam section is an initial read, not a commitment. Compiled 2026-06-28 from two deep-research workflows (recon: 7 angles, 86 sources, 14 deep-reads; control-substrate follow-up: 5 angles, 28 sources, 10 deep-reads).*

!!! note "Reading posture"
    Public facility pages are treated as the source of HARDWARE FACTS (beamline IDs, techniques, energies, detectors). Public GitHub/GitLab source and proceedings are treated as the source of CONTROL-SOFTWARE FACTS (what runs the scans, what talks to devices). Confidence is flagged inline as **[verified]** (multiple sources or a decisive primary), **[partly verified]**, or **[unconfirmed]**. The TOMCAT facility pages themselves name no control system, file format, or software version; the control-stack facts come from PSI-org and BEC-project source plus proceedings, tied back to TOMCAT where a TOMCAT-specific artifact exists. Per CORA's deployment-doc lens, the facility software stack is named ONLY at the seam (section 6): it is the floor CORA lands on or the orchestration CORA replaces, never a spec CORA mirrors.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | Swiss Light Source (SLS), storage-ring light source | [PSI SLS](https://www.psi.ch/en/sls) |
| Operator | Paul Scherrer Institute (PSI), Villigen, Switzerland | [PSI](https://www.psi.ch/en) |
| Beamline count | ~21 photon-science beamlines (PSI `X##xx` port IDs) | [Beamlines at SLS](https://www.psi.ch/en/sls/beamlines-at-sls) |
| Upgrade | SLS 2.0: seven-bend achromat (7BA) lattice; up to ~40x lower emittance, ~1000x brilliance; up to 4 orders of magnitude more data | [SLS 2.0](https://www.psi.ch/en/sls2-0) |
| Upgrade timeline | Machine dark time from Sept 2023; pilot users H2 2025; regular operation 2026; most beamlines operational by autumn 2026 | [SLS 2.0](https://www.psi.ch/en/sls2-0) |

**[verified]** SLS is a PSI storage-ring light source mid-upgrade to SLS 2.0 (7BA, ~40x emittance / ~1000x brilliance gain), with regular operation resuming through 2026.

The "up to four orders of magnitude more data" figure is the single most citable hook for CORA's data-of-record and debrief value proposition at this facility. **[verified]**

---

## 2. Candidate beamlines (tomography / imaging)

The historical TOMCAT imaging beamline (port X02DA) was rebuilt during SLS 2.0 into **two** successor beamlines, not one upgraded line. These are the natural first landing targets given CORA's imaging-tomography growth ladder (the same rung as the APS 2-BM and FXI exercises).

| Beamline | Port | Technique | Energy | Voxel / resolution | Endstations | First light | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **S-TOMCAT** | X02DA | Fast/flexible full-field tomography: absorption, propagation phase contrast, grating interferometry, 3D X-ray tomography | 8-80 keV white beam; mono restricted to 8-30 keV | 0.16-11 um voxel; up to 50 mm horizontal beam | 2 (17 m hutch) | 2025-06-25 | [S/I-TOMCAT beamlines](https://www.psi.ch/en/sls/tomcat/beamlines) |
| **I-TOMCAT** | X02SA | High-resolution / high-throughput / dynamic imaging | 8-50 keV mono (rec 8-30 until 2027) | 50 nm-1.1 um voxel | 3 (across 2 hutches, each with own control room) | 2025-09-25 | [S/I-TOMCAT beamlines](https://www.psi.ch/en/sls/tomcat/beamlines) |

- S-TOMCAT source: 5 T superconducting bend (white-beam). I-TOMCAT source: U15 undulator, planned upgrade to HTSU10 in 2027. **[verified]** [S/I-TOMCAT beamlines](https://www.psi.ch/en/sls/tomcat/beamlines)
- TOMCAT resumes regular user operations in Experimental Period 2026-II (proposal deadline 2026-03-16). [TOMCAT](https://www.psi.ch/en/sls/tomcat)
- **Five endstations total** across the two beamlines signals multiple concurrent acquisition contexts a CORA run/campaign model must accommodate.

**Detectors (imaging side, X02DA detectors page):** GigaFRoST (PSI in-house, continuous sustained streaming to a dedicated high-performance backend server), pco.edge 10/5.5/4.2 sCMOS, pco.dimax (legacy, mostly replaced by GigaFRoST); scintillators LuAG:Ce / LSO:Tb. Cameras stated as fully supported in the data acquisition and controls system. **[verified]** [TOMCAT detectors](https://www.psi.ch/en/sls/tomcat/detectors); GigaFRoST design [Mokso et al., J. Synchrotron Rad. 2017](https://doi.org/10.1107/S1600577517013522)

**Identifier-scheme note:** SLS uses PSI `X##xx` port IDs (e.g. X02DA), not the APS-style `sector.station` IDs CORA's 2-BM pilot assumes. This is a descriptor/identifier-scheme difference to model, not a hardware difference. **[verified]** [Beamlines at SLS](https://www.psi.ch/en/sls/beamlines-at-sls)

**Adjacent imaging-relevant SLS lines (context only, not primary targets):** cSAXS (X12SA) ptychography + SAXS 6-30 keV; Phoenix (X07MB) XAS + imaging; PolLux (X07DA) soft X-ray spectro-microscopy; SIM (X11MA) PEEM. [Beamlines at SLS](https://www.psi.ch/en/sls/beamlines-at-sls)

---

## 3. Control-system stack, by layer

PSI is an **EPICS (Channel Access / Process Variable)** facility, with PSI-grown IOC tooling, a beam-synchronous data sidecar (primarily SwissFEL), and a two-generation beamline scan-orchestration stack (pyscan, then BEC). The control substrate for the rebuilt TOMCAT beamlines specifically was the central open question of this research and is **resolved** below.

### Device IO / EPICS (the floor)

- **EPICS / Channel Access is the floor.** PSI maintains [StreamDevice](https://github.com/paulscherrerinstitute/StreamDevice) (generic byte-stream EPICS device support over serial/GPIB/TCP), [pcaspy](https://github.com/paulscherrerinstitute/pcaspy) (Channel Access server in Python for soft IOCs / derived PVs), and [s7plc](https://github.com/paulscherrerinstitute/s7plc) (Siemens S7 PLC driver for interlocks/slow control). These surface hardware as ordinary PVs. **[verified]**
- **PSI IOC framework: [`require` / driver.makefile](https://github.com/paulscherrerinstitute/require).** PSI's dynamic-module loader builds EPICS modules per (EPICS-base version x IOC architecture) into a shared module pool, loaded at runtime via the `require` command. This is below CORA's seam: it builds and version-pins the IOCs a CORA adapter would talk to. **[verified]**
- **Motion (SLS 2.0): ECMC** open-source EtherCAT motion control, adopted across PSI for SLS 2.0, complementing the ecat2 EPICS driver on the IOC side. **[verified]** [ECMC (inspirehep)](https://inspirehep.net/literature/3102887)
- **bsread beam-synchronous layer** (pulse-id-tagged ZMQ streams over mflow PUSH/PULL, DataBuffer / ImageBuffer dispatchers) is primarily SwissFEL (100 Hz pulsed) infrastructure; SLS storage-ring beamlines share the toolbox but historically lean on plain Channel Access. [bsread](https://github.com/paulscherrerinstitute/bsread), [bsread_python](https://github.com/paulscherrerinstitute/bsread_python). **[partly verified]** for the SLS-vs-SwissFEL split.

### Scan orchestration, two generations (the seam layer)

- **Generation 1: [pyscan](https://github.com/paulscherrerinstitute/pyscan)** a PSI library over Channel Access (`ca://`, set-and-match setpoint + readback with tolerance) and beam-synchronous data (`bs://`), with Positioner / Writable / Readable / Condition / Action types. Last active ~2018. **[verified]**
- **Generation 2: BEC (Beamline Experiment Control)** the SLS 2.0 standardized high-level scan engine. Modular cooperating microservices (scan_server, device_server, scan_bundler, file_writer, scihub, data_processing) coordinated over a Redis broker; drives EPICS/Channel Access through Ophyd (via [ophyd_devices](https://github.com/bec-project/ophyd_devices), `ophyd ~=1.10`, `pyepics ~=3.5`); writes NeXus/HDF5 via h5py. [BEC](https://github.com/bec-project/bec). **[verified]**

### TOMCAT control substrate: EPICS + BEC (confidence HIGH)

The rebuilt S-TOMCAT (X02DA) and I-TOMCAT (X02SA) run **EPICS Channel Access at the device floor, with PSI BEC as the orchestration layer above it.** The legacy TOMCAT/Concert (Tango) hypothesis is contradicted by all TOMCAT-specific evidence.

- **[TOMCAT-specific]** BEC's deployment registry names live PRODUCTION deployments for both endstations: `x02da-bec-001.psi.ch` (S-TOMCAT) and `x02sa-bec-001.psi.ch` (I-TOMCAT). [bec_atlas sls_deployments.yaml](https://github.com/bec-project/bec_atlas/blob/main/backend/bec_atlas/deployment/realms/sls_deployments.yaml); x-name->beamline map (`x02da: (S-TOMCAT, TOMCAT)`, `x02sa: (I-TOMCAT,)`) in [bec_atlas model.py](https://github.com/bec-project/bec_atlas/blob/main/backend/bec_atlas/model/model.py).
- **[TOMCAT-specific]** TOMCAT device code lives in the EPICS/ophyd device repo: changelog entry "Add detector, grashopper tomcat to repository"; deps are `ophyd` + `pyepics` (Channel Access), no Tango. [ophyd_devices CHANGELOG](https://github.com/bec-project/ophyd_devices/blob/main/CHANGELOG.md).
- **[TOMCAT-specific]** A dedicated `tomcat_bec` plugin exists alongside other PSI beamline BEC plugins (csaxs_bec, microxas_bec, etc.). [plugin_copier_template](https://github.com/bec-project/plugin_copier_template/blob/main/utility_scripts/manual_update.sh).
- **[TOMCAT-specific]** NOBUGS 2024 talk "Controls for dynamic tomography at the TOMCAT beamlines" (I. Mohacsi, PSI): the I- and S-TOMCAT beamlines interface "with the data path and other sub-systems via EPICS and a new high-level beamline experimental control system"; architecture = an EtherCAT-based motion backbone plus custom systems for high-speed motion, synchronization, and triggering. [ESRF Indico](https://indico.esrf.fr/event/114/contributions/831/).
- **[org-wide]** SLS 2.0 facility decision: the control system continues to be EPICS-based, EPICS 7 only, "only channel access protocol will remain to be supported on day one." [ICALEPCS 2023 TUPDP105](https://proceedings.jacow.org/icalepcs2023/papers/tupdp105.pdf). BEC is the mandated post-upgrade experiment control for ALL SLS beamlines, built on Bluesky/Ophyd. [CaSIT FR1BCO04](https://inspirehep.net/files/f1110bf966acfe240d1313c3f99f90cb), [ICALEPCS 2023 MO2AO02](https://proceedings.jacow.org/icalepcs2023/papers/mo2ao02.pdf).

**Contrary evidence weighed and rejected:** [Concert](https://github.com/ufo-kit/concert) (ufo-kit) remains Tango-based and active (v0.33.0, Apr 2025), but is a KIT/ANKA-KARA project; its code search returns 34 Tango / 0 EPICS / 0 TOMCAT mentions. Tango appears in BEC's documentation only as a hardware-abstraction-evaluation aside (BLISS was evaluated then rejected in favour of Bluesky/Ophyd). The premise that Concert is TOMCAT's current acquisition layer is unverified and contradicted. **[verified]**

This refines the cross-facility survey's earlier PSI read (acquisition listed as "PShell + EPICS + BSREAD, control TBD"): for the SLS 2.0 photon beamlines the orchestration is BEC, not PShell.

### Signal-level confirmation (device-mining pass)

A third workflow mined the public BEC source (`ophyd_devices`, `bec_atlas`) to confirm the floor at the signal level, not just by inference. Findings:

- **EPICS Channel Access is the floor, confirmed at the signal level.** The shared PSI motor bases all subclass ophyd `EpicsMotor` / `EpicsSignalBase` over MotorRecord PV suffixes: `EpicsMotor`, `EpicsMotorEC` (ECMC suffixes `-EnaAct` / `-PosAct` / `-VelAct` / `-PosErr` / `-SumIlockFwd`), `EpicsUserMotorVME`, `PSIPositionerBase`. [psi_motor.py](https://github.com/bec-project/ophyd_devices/blob/main/ophyd_devices/devices/psi_motor.py), [psi_positioner_base.py](https://github.com/bec-project/ophyd_devices/blob/main/ophyd_devices/interfaces/base_classes/psi_positioner_base.py). Area-detector cameras use `EpicsSignalWithRBV` over PV suffixes ([cam.py](https://github.com/bec-project/ophyd_devices/blob/main/ophyd_devices/devices/areadetector/cam.py)); the SLS ring monitor reads `ARIDI-PCT:CURRENT`. The public deployment template carries a CA-gateway env line (`EPICS_CA_ADDR_LIST = "129.129.122.255 sls-x12sa-cagw.psi.ch:5836"`). **[verified]**
- **Tomography rotation lineage.** `EpicsRotationBase(OphydRotationBase, EpicsMotor)` exposes rotation modes `["target", "radiography"]` and `allow_mod360`; it was added in the same commit as the (now-removed) `tomcat_rotation_motors.py`, so it is the surviving generic base the concrete TOMCAT rotation axis subclassed. [ophyd_rotation_base.py](https://github.com/bec-project/ophyd_devices/blob/main/ophyd_devices/interfaces/base_classes/ophyd_rotation_base.py). **[verified]** for the base; the concrete axis is firewalled (section 6).

**Fast-path caveat, now concrete [verified for PandABox]:** the fly-scan trigger surface `PandaBox` is NOT EPICS. It uses `import socket` + the `pandablocks` library + a raw data socket (`connect(host, 8889)`); its `*IDN?` / `SEQ1.TABLE>` strings are PandABox ASCII protocol commands, not EPICS PVs. [panda_box.py](https://github.com/bec-project/ophyd_devices/blob/main/ophyd_devices/devices/panda_box/panda_box.py). So CORA's ControlPort at TOMCAT must span EPICS Channel Access plus at least one direct-socket adapter, the same heterogeneous-control-plane shape seen at MX3 (EPICS + Exporter + REST). TOMCAT's signature **GigaFRoST** camera has no public source class anywhere (no `gigafrost` path, no changelog mention), so whether it is an EPICS areaDetector device, a socket fast-path, or firewalled is an open question. EtherCAT/PSO triggering specifics are likewise not determinable from public source.

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| [paulscherrerinstitute](https://github.com/paulscherrerinstitute) (GitHub, ~258 repos) | EPICS device support, IOC framework, DAQ microservices, bsread, scicat-cli, py_elog | [org](https://github.com/paulscherrerinstitute) |
| [bec-project](https://github.com/bec-project) (GitHub) | BEC scan engine, ophyd_devices, bec_atlas deployment registry, plugin templates | [bec](https://github.com/bec-project/bec) |
| [slsdetectorgroup](https://github.com/slsdetectorgroup) (GitHub) | slsDetectorPackage (Eiger/Jungfrau/Mythen/Gotthard/Moench) control + DAQ | [slsDetectorPackage](https://github.com/slsdetectorgroup/slsDetectorPackage) |
| [SciCatProject](https://github.com/SciCatProject) (GitHub) | SciCat catalog backend/frontend, ingestor, scitacean | [backend](https://github.com/scicatproject/backend) |
| [dectris](https://github.com/dectris) (GitHub) | DECTRIS SIMPLON / stream_v2 / NXmx filewriter (EIGER2/PILATUS4) | [documentation](https://github.com/dectris/documentation) |
| [ufo-kit](https://github.com/ufo-kit) (GitHub) | UFO/tofu GPU reconstruction; Concert (Tango, not TOMCAT) | [ufo-core](https://github.com/ufo-kit/ufo-core) |
| `gitea.psi.ch` (internal) | The private `tomcat_bec` plugin and production deployment configs | named, not reachable |

**[partly verified]** PSI's own GitLab/Gitea is not publicly resolvable; the public GitHub repos may not be the full deployment source of record. The private `tomcat_bec` plugin is the authoritative per-beamline config.

**Why a full device model is not yet integrity-buildable from public source.** The device-mining pass established that TOMCAT sits with ALBA and Sirius (device source of record firewalled), not with the reverse-engineered beamlines (MX3, Diamond, SLAC) whose public device libraries expose real PVs:

- The only TOMCAT-named files (`grashopper_tomcat.py` = a FLIR/Point Grey Grasshopper camera, `tomcat_rotation_motors.py`, `aerotech/AerotechAutomation1.py`) were added then **removed** from `ophyd_devices`; they are 404 on `main` and survive only in git history (added in `ddd0b79`, removed in `ce43924` "Cleanup aerotech"). The on-main tree carries only shared PSI base classes, not the concrete TOMCAT devices.
- [`bec_atlas/sls_deployments.yaml`](https://github.com/bec-project/bec_atlas/blob/main/backend/bec_atlas/deployment/realms/sls_deployments.yaml) names both realms (`x02da`, `x02sa`), deployment hosts (`x02da-bec-001.psi.ch`, `x02sa-bec-001.psi.ch`, both production), and access groups (`unx-sls_x02da_bs`), but binds **zero** devices or PVs. The device list lives in the runtime `Session.device_config_collections`, populated from the firewalled deployment and MongoDB.
- The `tomcat_bec` plugin (the concrete device classes, `device_configs/*.yaml` PV wiring, and tomography scan plans) is hosted on `gitea.psi.ch` and is not public.

Building an `inventory.md` / `model.md` from the shared base classes alone would require mapping a generic class to "the TOMCAT device," which is inference, not source, and is therefore deliberately not done. The device model is an open item for the staff questions below.

---

## 5. Data management

PSI's data ecosystem centers on **SciCat**, wired to the **DUO** user office and a **CSCS**-hosted tape archive. SciCat originated at PSI (co-developed with ESS and MAX IV, EU H2020 BrightnESS grant 676548), which makes it the closest public analog to CORA's "system of record for the experiment" positioning, and the key seam tension at this facility.

- **SciCat catalog** (NestJS/TypeScript backend v4.x on MongoDB, BSD-3-Clause): raw vs derived Datasets; OrigDatablock (original path) vs Datablock (archive path/archiveId); DataFiles with checksums; ownership via ownerGroup/accessGroups; links to Proposal/Sample/Instrument/Techniques; PublishedData/DOI via DataCite; archive packaging/retrieve tracked as Jobs in DatasetLifecycle. PSI surfaces: [discovery.psi.ch](https://discovery.psi.ch/) (catalog UI), [doi.psi.ch](https://doi.psi.ch/) (public DOI repository). **[verified]** [SciCat backend](https://github.com/scicatproject/backend), [SciCat Data Model v4.x](https://www.scicatproject.org/documentation/Development/v4.x/Data_Model.html)
- **DUO / proposals / p-groups** ([duo.psi.ch](https://duo.psi.ch/)): a proposal yields a p-group which becomes the SciCat ownerGroup, controlling dataset access. **[verified]**
- **Ingestion pipeline** ([scicat-ingestor](https://github.com/SciCatProject/scicat-ingestor)): consumes Kafka `wrdn` (write-done) messages from the file-writer and ingests the corresponding NeXus/HDF5 files, creating raw Datasets + OrigDatablocks via the SciCat API. **[verified]**
- **File formats:** NeXus on HDF5 is the ingested format; BEC's file_writer produces NeXus/HDF5. PSI follows a FAIR-compatible data policy with an embargo period, public on peer-reviewed publication. **[partly verified]** (TOMCAT-specific writer + on-disk layout unconfirmed.)
- **Archive:** PetaByte tape-based long-term storage at CSCS (Lugano); SciCat orchestrates packaging/archive/retrieve as Jobs; transfer via `datatransfer.psi.ch`. **[partly verified]** (one URL slug inferred.)

---

## 6. The CORA seam (initial read)

First pass, not a committed seam. Applies the 2-BM/FXI lens: EPICS and device IO are the floor CORA never replaces; the higher scan/orchestration layer is where CORA replaces or drives through; the facility catalog is a source-of-truth contest, not a dependency.

**Where EPICS stays the floor (drive through, never CORA).** TOMCAT device IO is EPICS Channel Access (ophyd-backed under BEC), with StreamDevice/pcaspy/s7plc device support, `require`-built IOCs, ECMC/ecat2 EtherCAT motion, and the detector edge (slsDetectorPackage, GigaFRoST, DECTRIS SIMPLON). CORA's ControlPort would actuate **through** this EPICS floor exactly as at 2-BM and FXI; CORA never owns PVs, IOCs, or the device layer. The accelerator-side EPICS stack and floor-level fast-data transport (bsread/mflow, DataBuffer/ImageBuffer) are out of scope. **Because the floor is EPICS, the APS-pilot ControlPort model carries over with no new control substrate to build.**

**What CORA replaces (edge orchestration).** The scan/alignment orchestration role is held today by **PSI BEC** (scan_server / device_server) and, in the prior generation, pyscan. This is the layer the 2-BM seam designates as CORA's: CORA's EdgeConductor would conduct routines over the EPICS floor where BEC's scan orchestration sits today, incrementally and routine-by-routine, the same shape as the 2-BM replace-TomoScan-orchestration decision. A BEC-deployed beamline is the "replacing a solid existing implementation" case: treat BEC as DATA to learn from (its component decomposition, NeXus structure, Ophyd device abstraction), NOT a spec to mirror. Pitch CORA conducting on governance, replayability, recipe-binding, and simplicity, never on out-executing BEC or pyscan on speed (CORA is barred from the deterministic real-time loop by construction; the produced record is identical regardless of the execution layer underneath).

**Source-of-truth contest (data).** SciCat is the sharpest seam, because PSI is SciCat's home institution and SciCat claims the same metadata-catalog-of-record territory CORA claims for the experiment. CORA does NOT drive through SciCat the way it drives through EPICS. Either CORA inverts source-of-truth and feeds SciCat as a downstream publish/export target (at the `wrdn`-Kafka publish seam), or, where SciCat is mandated, projects its event-sourced record into SciCat at the publish seam. CORA stays the system of record for the experiment (decisions, recipe ladder, provenance, trust); the facility catalog is named only at the seam. CORA owns its own data-of-record (PG event store); the NeXus/HDF5 output and SciCat catalog are a source to subsume, not a dependency. Decision deferred until a SciCat-running deployment is actually in scope.

**Coexist.** DUO (facility scheduling/identity; read the user roster and p-group via an ACL adapter, record proposal context as the Campaign/Run correlation key; do not replace), the UFO/tofu reconstruction compute (a JobRunnerPort roundtrip CORA governs but does not own), the CSCS archive (an egress destination), and ELOG/scilog logbooks (record-keeping overlap CORA subsumes at the debrief layer rather than adopting).

---

## 7. Open questions (for PSI staff)

These could not be settled from public sources and need operator confirmation before any seam lock. Ask **Istvan Mohacsi (PSI, TOMCAT controls)** or the PSI BEC/Controls team; the private `tomcat_bec` plugin (gitea.psi.ch) and GigaFRoST integration code would settle most.

1. **Fast-path substrate:** which TOMCAT signals are EPICS `EpicsSignal` versus direct-socket? Does the high-speed triggering/motion path (EtherCAT, GigaFRoST, PSO) bypass EPICS? This bounds the ControlPort surface.
2. **BEC service footprint per beamline:** which BEC services (scan_server, device_server, file_writer, scihub) run on S-TOMCAT vs I-TOMCAT today?
3. **Acquisition writer + format:** does the GigaFRoST/pco streaming backend write NeXus/HDF5, via which writer (BEC file_writer, a TOMCAT-custom backend), and what is the on-disk layout and frame rate?
4. **Detector control contract per endstation:** which cameras/detectors and which driver path (areaDetector/EPICS, slsDetectorPackage, DECTRIS SIMPLON, GigaFRoST backend) per endstation?
5. **SciCat seam:** is dataset ingestion into SciCat mandatory for TOMCAT proposals, and at what point (the `wrdn` Kafka message)? This decides invert-vs-project.
6. **Identity chain:** is DUO -> p-group -> SciCat ownerGroup the authoritative access-control chain CORA must read, and via which API?
7. **Reconstruction in the loop:** is online reconstruction (UFO/tofu real-time content-based feedback, per the TOMCAT literature) part of routine operations CORA's orchestration would coordinate, and on what compute (local GPU, CSCS)?
8. **Identifier mapping:** confirm the `X##xx` port IDs and how endstation/hutch (2 on S-TOMCAT, 3 across 2 hutches on I-TOMCAT) map to CORA's run/acquisition-context identifiers.

---

## 8. Source list

**Facility (hardware facts):**
- SLS: https://www.psi.ch/en/sls
- Beamlines at SLS: https://www.psi.ch/en/sls/beamlines-at-sls
- TOMCAT: https://www.psi.ch/en/sls/tomcat
- S-TOMCAT and I-TOMCAT beamlines: https://www.psi.ch/en/sls/tomcat/beamlines
- TOMCAT detectors: https://www.psi.ch/en/sls/tomcat/detectors
- SLS 2.0 upgrade: https://www.psi.ch/en/sls2-0

**Control substrate (TOMCAT-specific):**
- BEC Atlas SLS deployments (x02da/x02sa production): https://github.com/bec-project/bec_atlas/blob/main/backend/bec_atlas/deployment/realms/sls_deployments.yaml
- BEC Atlas x-name->beamline model: https://github.com/bec-project/bec_atlas/blob/main/backend/bec_atlas/model/model.py
- ophyd_devices (TOMCAT device code, pyepics dep): https://github.com/bec-project/ophyd_devices
- BEC scan engine: https://github.com/bec-project/bec
- plugin_copier_template (tomcat_bec plugin): https://github.com/bec-project/plugin_copier_template
- NOBUGS 2024, Controls for dynamic tomography at TOMCAT (Mohacsi): https://indico.esrf.fr/event/114/contributions/831/

**Control system (PSI floor + proceedings):**
- StreamDevice: https://github.com/paulscherrerinstitute/StreamDevice
- pcaspy: https://github.com/paulscherrerinstitute/pcaspy
- s7plc: https://github.com/paulscherrerinstitute/s7plc
- require / driver.makefile: https://github.com/paulscherrerinstitute/require
- pyscan (gen-1): https://github.com/paulscherrerinstitute/pyscan
- bsread: https://github.com/paulscherrerinstitute/bsread
- bsread_python: https://github.com/paulscherrerinstitute/bsread_python
- cam_server: https://github.com/paulscherrerinstitute/cam_server
- std_daq_service: https://github.com/paulscherrerinstitute/std_daq_service
- detector_integration_api: https://github.com/paulscherrerinstitute/detector_integration_api
- PSI GitHub org: https://github.com/paulscherrerinstitute
- SLS 2.0 Beamline Control System Upgrade Strategy (ICALEPCS 2023 TUPDP105): https://proceedings.jacow.org/icalepcs2023/papers/tupdp105.pdf
- BEC / HAL evaluation (ICALEPCS 2023 MO2AO02): https://proceedings.jacow.org/icalepcs2023/papers/mo2ao02.pdf
- Controls and Science IT for SLS 2.0 (CaSIT FR1BCO04): https://inspirehep.net/files/f1110bf966acfe240d1313c3f99f90cb
- ECMC EtherCAT motion control: https://inspirehep.net/literature/3102887
- Concert (Tango; KIT/ANKA, not TOMCAT): https://github.com/ufo-kit/concert

**Detectors:**
- slsDetectorPackage: https://github.com/slsdetectorgroup/slsDetectorPackage
- DECTRIS documentation (SIMPLON / stream_v2 / NXmx): https://github.com/dectris/documentation
- GigaFRoST (Mokso et al., J. Synchrotron Rad. 2017): https://doi.org/10.1107/S1600577517013522

**Data management:**
- SciCat backend: https://github.com/scicatproject/backend
- SciCat Data Model v4.x: https://www.scicatproject.org/documentation/Development/v4.x/Data_Model.html
- scicat-ingestor: https://github.com/SciCatProject/scicat-ingestor
- scicat-cli (PSI): https://github.com/paulscherrerinstitute/scicat-cli
- discovery.psi.ch (catalog UI): https://discovery.psi.ch/
- doi.psi.ch (DOI repository): https://doi.psi.ch/
- DUO (user office): https://duo.psi.ch/
- CSCS (archive host): https://www.cscs.ch/

**Reconstruction (TOMCAT lineage):**
- UFO ufo-core: https://github.com/ufo-kit/ufo-core
- UFO ufo-filters: https://github.com/ufo-kit/ufo-filters
- tofu: https://github.com/ufo-kit/tofu
- On-the-fly post-processing at TOMCAT (Marone et al. 2017): https://doi.org/10.1186/s40679-016-0035-9
- Real-time reconstruction + feedback at TOMCAT (Buurlage et al. 2019): https://doi.org/10.1038/s41598-019-54647-4
- Real-time image-content-based beamline control (Vogelgesang et al. 2016): https://doi.org/10.1107/S1600577516010195

**Internal-only (named, not reachable):** `gitea.psi.ch` (tomcat_bec plugin, deployment configs), `datatransfer.psi.ch`.
