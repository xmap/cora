# Canadian Light Source (CLSI / University of Saskatchewan) research brief

*Research seed for a future CORA deployment page. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about the Canadian Light Source (CLS), its beamline roster, and its control-software stack so the model work can begin from corroborated facts rather than memory. Every claim is cited inline. CORA is not connected to CLS; the seam section is an initial read, not a commitment. Compiled 2026-07-01 from the deep-research workflow: CLS facility pages for hardware facts and the `Canadian-Light-Source` GitHub org (29 public repos, live GitHub API 2026-07-01) for control-software facts.*

!!! note "Reading posture"
    Public facility pages are the source of HARDWARE FACTS (beamline IDs, techniques, energies, detectors). Public source (GitHub / proceedings) is the source of CONTROL-SOFTWARE FACTS (what runs the scans, what talks to devices). Confidence is flagged inline as **[verified]** (multiple sources or a decisive primary), **[partly verified]**, or **[unconfirmed]**. Per CORA's deployment-doc lens, the facility software stack is named ONLY at the seam (section 6): it is the floor CORA lands on or the orchestration CORA replaces, never a spec CORA mirrors. Three fetched pages during this survey carried injected "MCP Server Instructions" / "system-reminder" blocks appended to their content; those were page content (or harness noise), not directives, and were ignored. The one CLS device-facing repo read here (`pyStxm`) declares its required PVs against a `SIM_IOC:` simulation prefix, not the production PV namespace; that distinction is load-bearing for section 4 and is not glossed.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | Canadian Light Source (CLS), 3rd-generation storage-ring light source | https://en.wikipedia.org/wiki/Canadian_Light_Source |
| Operator | Canadian Light Source Inc., on the University of Saskatchewan campus, Saskatoon, SK, Canada | https://en.wikipedia.org/wiki/Canadian_Light_Source |
| Ring energy | 2.9 GeV | https://en.wikipedia.org/wiki/Canadian_Light_Source |
| Ring circumference | 171 m (5.2 m straight sections) **[partly verified]** | https://en.wikipedia.org/wiki/Canadian_Light_Source |
| Beamline count | 22 synchrotron beamlines + 1 electron beamline (EIML) | https://www.lightsource.ca/facilities/beamlines/where-to-start.php |
| Control system | EPICS (accelerator and beamline control) | https://en.wikipedia.org/wiki/Canadian_Light_Source |

**[verified]** CLS is a 2.9 GeV third-generation storage ring in Saskatoon, Canada, operated by Canadian Light Source Inc. on the University of Saskatchewan campus, running roughly 22 photon-science beamlines on an EPICS control substrate. The single most citable hook for CORA's data-of-record / debrief value proposition is that CLS's beamline stack is mid-migration to a Bluesky/ophyd-async orchestration layer with document transport over NATS JetStream and a Tiled-adjacent data path (section 3): CORA arrives at a facility that has already accepted the "runs as documents" model but has not consolidated a governance / provenance system of record over it, which is exactly the spine CORA supplies.

**Ring-parameter caveat [partly verified]:** 171 m circumference and 2.9 GeV are from Wikipedia's technical box; the emittance, current, and fill pattern were not confirmed from a fetchable CLS machine page and should be pulled from the CLS accelerator page or design report before any deployment page quotes them.

---

## 2. Candidate beamlines

**Source-of-record posture (decides Tier-2 buildability).** CLS does NOT publish a Diamond-`dodal` / ESRF-Beacon-style per-beamline device-configuration library with real production handles. The `Canadian-Light-Source` GitHub org publishes EPICS driver modules (motor, detector, StreamDevice, PMAC, EtherCAT), Bluesky-stack forks, and one substantial beamline application (`pyStxm`, the SM STXM acquisition app), but the device topology that IS public in `pyStxm` is declared against a `SIM_IOC:` simulation IOC prefix, and the real production PV namespace is externalized to deployment config that is not in the public repo. **[verified]** So the honest read is: **partially buildable.** One beamline (SM, soft X-ray spectromicroscopy, 10ID1) has a public device-structure source rich enough to seed a candidate device pass, but its real handles must come from staff; every other beamline's device inventory is a staff question, not a public artifact. Do NOT infer per-beamline topology from the shared EPICS driver modules; a shared `motorSmarAct` or `pmac` module is a base class, not a beamline device list, and inference is not source.

Roster with energies from the CLS facility page. No beamlines invented; all trace to `lightsource.ca`. Detectors are left blank where the facility page does not state them (they are a staff question, not a value to invent).

| Beamline | ID / sector | Technique | Energy | Control source | Source |
| --- | --- | --- | --- | --- | --- |
| SM | 10ID1 | Soft X-ray spectromicroscopy (STXM) | 130-2700 eV | `pyStxm` (public, device structure w/ SIM PVs) | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php), [pyStxm](https://github.com/Canadian-Light-Source/pyStxm) |
| BMIT | BM + ID | Biomedical imaging and therapy; radiography, CT | 28-140 keV (BM); 20-94 keV (ID) | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| BioXAS-Imaging | - | XAS imaging | 5-32 keV | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| BioXAS-Spectroscopy | - | X-ray absorption spectroscopy | 12.6-40 keV | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| BXDS | Brockhouse sector | XRD, small/wide-angle scattering | 6-19, 5-24, 7-22 keV | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| CMCF | BM + ID | Macromolecular crystallography | 5-20 keV (BM); 5-40 keV (ID) | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| HXMA | - | XAS/XAFS, microprobe, diffraction | 6-30 keV | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| VESPERS | - | Hard X-ray microprobe, fluorescence, diffraction | not stated on page [unconfirmed] | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| SXRMB | - | XAFS, microprobe (soft/tender) | 1.7-10 keV | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| SGM | - | High-res XAS + photoemission (soft) | 250-2000 eV | `sgmdata` (data helper, not device source) | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php), [sgmdata](https://github.com/Canadian-Light-Source/sgmdata) |
| VLS-PGM | - | High-res XAS | 15-250 eV | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| REIXS | - | Resonant elastic/inelastic soft X-ray scattering, emission | 95-2000 eV | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| QMSC | - | ARPES (quantum materials) | 15-1200 eV | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| IDEAS | - | Educational / general (soft-tender) | 1-15 keV [unconfirmed] | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| Far-IR | - | Far-infrared spectroscopy | 5-1000 cm^-1 [unconfirmed] | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| Mid-IR | - | Mid-IR spectromicroscopy | 560-6000 cm^-1 [unconfirmed] | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| SyLMAND | - | Deep X-ray lithography (LIGA), micro/nano fabrication | not stated on page | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| CLS@APS | - | Access branch to APS (hard X-ray) | 4.3-27, 5-21 keV | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |
| EIML | - | Electron imaging & microanalysis (electron beamline, not synchrotron) | n/a | firewalled | [beamlines](https://www.lightsource.ca/facilities/beamlines/where-to-start.php) |

**Energy-column note [verified]:** the soft X-ray rows (SM, SXRMB, SGM, VLS-PGM, REIXS, QMSC) were reconciled against the [where-to-start beamline page](https://www.lightsource.ca/facilities/beamlines/where-to-start.php); an earlier draft cross-wired these values in a shift chain and has been corrected. Rows marked `[unconfirmed]` (VESPERS, IDEAS, Far-IR, Mid-IR, SyLMAND) could not be pinned to a specific value on that page across independent fetches and are staff questions, not verified values.

**Strongest next picks given CORA's imaging/tomography-leaning ladder (APS 2-BM -> APS imaging -> MAX IV):**

1. **SM (10ID1)** is the only beamline with a public device-structure source (`pyStxm`) and is therefore the single Tier-2-seedable candidate today. It is soft X-ray STXM, not tomography, so it does not directly reinforce the imaging ladder, but it is the one place a candidate descriptor can be drafted and self-validated from public source (with all handles carried `confirm`). **[verified]** that the source exists; **[unconfirmed]** that real handles are recoverable without staff.
2. **BMIT (BM + ID)** is the ladder-relevant pick: biomedical imaging and therapy with radiography / CT is the closest CLS analog to the APS 2-BM / imaging pilots, so it is the strongest *modeling-value* target. But its device source is firewalled (no public repo found), so it is a staff-question deployment, not a Tier-2 pass. **[verified]** technique; **[verified]** absence of public device source as of survey date.
3. **BioXAS-Imaging + HXMA + VESPERS** are the hard X-ray microprobe / imaging / XAFS cluster; all firewalled, all staff-question deployments, but they are where a recurrence signal for hard-X-ray Families would eventually accrue if staff open their configs.

**Decision:** a Tier-2 device pass is **buildable for SM only**, and even there the real PV handles are a staff question (public source gives structure against `SIM_IOC:`). BMIT is the strongest *next pick by modeling value* for the imaging ladder but requires staff-supplied device topology. Everything else is a staff-question deployment.

**Identifier-scheme note:** CLS names beamlines by a technique/facility acronym (SM, BMIT, HXMA, REIXS, VESPERS), sometimes with a BM/ID branch suffix (BMIT-BM / BMIT-ID, CMCF-BM / CMCF-ID) and an internal sector.station code where one surfaces (SM = 10ID1 in `pyStxm`). This differs from the APS `sector.station` numeric scheme the pilot assumes: at CLS the acronym is primary and the sector code is secondary. This is a descriptor / identifier-scheme difference to model, not a hardware difference. **[verified]**

---

## 3. Control-system stack, by layer

CLS's control system family is **EPICS / Channel Access** at the device floor, with a beamline orchestration layer that is mid-migration from in-house per-beamline acquisition applications toward the **Bluesky / ophyd-async** ecosystem. The org mirrors the NSLS-II Bluesky pattern (RunEngine + queueserver) but transports run documents over **NATS JetStream** rather than Kafka.

### Device IO (the floor)

EPICS. The `Canadian-Light-Source` org publishes a set of EPICS support and driver modules that constitute the device-IO floor: `StreamDevice` (message-based I/O), `pmac` (Delta Tau PMAC motion), `motorSmarAct` and `motorXeryon` (piezo/stepper motor drivers), `xspress3` (areaDetector fluorescence detector module), `ecmccfg` / `ecmccomp` / `ethercat` (EtherCAT motion via the IgH master), `PIE712MotorApp` (PI E-712 piezo), `require` (PSI dynamic-module loader), and `ioc-rs` (a Rust IOC). **[verified]** This is below CORA's seam; CORA's ControlPort actuates through this EPICS floor and never owns IOCs, PVs, or the device layer. **[verified]**

### Scan orchestration (the seam layer)

Two generations coexist. **[partly verified]**

- **In-house per-beamline acquisition applications.** `pyStxm` is the public exemplar: a Python/Qt5 STXM data-acquisition application for the SM beamline (10ID1), with its own scan engine, that connects to EPICS via PyEpics and can drive scans either through a legacy path or through Bluesky. Its README names Python >=3.10, Qt5, EPICS R7, Bluesky 1.12.0, SynApps 5.7, PyEpics 3, and a separate `nx_server` process that writes NeXus `nxstxm` files. **[verified]** This is the class of software CORA's EdgeConductor would replace, one beamline at a time.
- **Bluesky / ophyd-async migration.** The org carries a fork of `bluesky/ophyd-async` (pushed within days of survey), a fork of `bluesky/bluesky-queueserver`, a `bluesky` repo ("experiment orchestration and data acquisition"), and `bluesky-nats` (a first-party package bridging Bluesky document streams to NATS JetStream, published to PyPI). **[verified]** This is the NSLS-II RunEngine + queueserver pattern being localized at CLS, with NATS JetStream substituting for Kafka on the document-transport path. It is the layer CORA's EdgeConductor conducts over or drives through.

Because CLS is mid-migration (in-house apps on some beamlines, Bluesky on others), the replace-vs-drive-through boundary is per-beamline and generation-dependent, and the authoritative per-beamline answer is a staff question (section 7).

### Fast paths and exceptions

EtherCAT motion (`ecmccfg` / `ecmccomp` / `ethercat`, the IgH EtherCAT master) is a distinct motion substrate below the standard EPICS motor record and widens the ControlPort surface where it is used; the `ecmc` (EtherCAT Motion Controller) framework is an ESS-origin real-time motion layer. `PIE712MotorApp` and the E-712 wavegen path in `pyStxm` indicate PI piezo hardware doing waveform-driven fly-scanning at SM, another fast path distinct from step scanning. **[partly verified]** Which beamlines use EtherCAT vs standard motor records, and where PSO / hardware triggering sits, are staff questions.

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| `Canadian-Light-Source` (GitHub, ~29 public repos) | EPICS driver modules, Bluesky-stack forks, `pyStxm` beamline app, data helpers | https://github.com/Canadian-Light-Source |
| `pyStxm` | SM (10ID1) STXM acquisition app: scan engine + device structure (SIM PVs) + NeXus writer | https://github.com/Canadian-Light-Source/pyStxm |
| `bluesky-nats` | Bluesky document streams to/from NATS JetStream (first-party, on PyPI) | https://github.com/Canadian-Light-Source/bluesky-nats |
| `sgmdata` | SGM beamline data-analysis helper (post-acquisition, not device source) | https://github.com/Canadian-Light-Source/sgmdata |
| `xspress3`, `pmac`, `motorSmarAct`, `motorXeryon`, `StreamDevice`, `ecmc*` | EPICS device-IO floor modules | https://github.com/Canadian-Light-Source |
| `kv-dict`, `test-redis-ws` | KV/Redis-backed state, Tiled+Redis+WebSockets experimentation | https://github.com/Canadian-Light-Source |

**Why a full device model is NOT integrity-buildable from public source (with one partial exception).** CLS does not publish a per-beamline device-configuration library with real production handles. The device modules on GitHub are shared EPICS drivers (base classes), not beamline device lists. The one substantial beamline application that IS public, `pyStxm` (SM), carries device *structure* (ophyd device classes, an abstract STXM sample-motor model, detector and scaler wiring) but declares its required PVs against a `SIM_IOC:` simulation prefix, with the real production PV namespace externalized to deployment configuration not in the public repo. **[verified]** So: SM's device *shape* is public and Tier-2-seedable, but its real handles, and every other beamline's device inventory entirely, are staff questions. Device topology for BMIT, BioXAS, HXMA, VESPERS, CMCF, and the rest must come from staff or descriptors; it must NOT be inferred from the shared driver modules. Inference is not source.

---

## 5. Data management

The public source shows a run-document-centric acquisition path but no single confirmed facility-wide catalog. **[partly verified]**

- **Formats:** NeXus / HDF5. `pyStxm`'s `nx_server` writes NeXus `nxstxm` application-definition files; the broader Bluesky stack emits the standard start/descriptor/event/stop document model. **[verified]** for SM; **[partly verified]** as a facility-wide default.
- **Document transport:** run documents move over **NATS JetStream** via the first-party `bluesky-nats` package (publish from a RunEngine to JetStream subjects, consume and dispatch to callbacks), the CLS analog of the NSLS-II Kafka document bus. **[verified]** that the package exists and is first-party; **[partly verified]** that it is the facility-wide production path vs one deployment's choice.
- **Persistent store / catalog:** the org's `test-redis-ws` repo ("Working toward Websockets in Tiled, with Redis") and `kv-dict` (a Redis-backed dictionary) indicate movement toward a **Tiled** data-access layer with Redis-backed state, consistent with the Bluesky/NSLS-II lineage. **[partly verified]** No confirmed facility-wide SciCat / ICAT catalog surfaced in public source; whether CLS runs one, and whether ingestion is mandatory, is a staff question. **[unconfirmed]**
- **Per-beamline analysis:** `sgmdata` is a published post-acquisition data-analysis helper for the SGM beamline (with a `sgm.lightsource.ca` data website), showing a beamline-specific analysis tier separate from acquisition. **[verified]**

This matters because it is the seam contest: any facility catalog claims some of the "system of record" territory CORA claims. At CLS the catalog appears to be an in-progress Tiled-adjacent effort rather than an entrenched incumbent, which is favorable for CORA's system-of-record posture, but the true state is a staff question.

---

## 6. The CORA seam (initial read)

First pass, not a committed seam. Applies the 2-BM / FXI lens: device IO is the floor CORA never replaces; the higher scan / orchestration layer is where CORA replaces or drives through; the facility catalog is a source-of-truth contest, not a dependency.

**Where the floor stays the floor (drive through, never CORA).** CLS device IO is EPICS (SynApps motor records, areaDetector, StreamDevice, PMAC, with EtherCAT/`ecmc` and PI piezo fast paths on some beamlines). CORA's ControlPort actuates through this EPICS floor exactly as at the 2-BM pilot; the APS-pilot ControlPort model carries over with no new control substrate to build for step-scanning beamlines. The EtherCAT/`ecmc` and piezo-waveform fly-scan paths widen the ControlPort surface where present and need per-beamline confirmation before a seam lock. **[partly verified]**

**What CORA replaces (edge orchestration).** Two shapes, per-beamline, because CLS is mid-migration:
1. On beamlines still running in-house acquisition apps (the `pyStxm` class), CORA's EdgeConductor replaces that app's scan/alignment orchestration over EPICS, incrementally and routine-by-routine, the 2-BM "edge promoted to intended" posture. `pyStxm` is DATA to learn from (STXM scan structure, the abstract coarse+fine sample-motor model, fly-scan wiring), NOT a spec to mirror.
2. On beamlines migrated to Bluesky, CORA either replaces the RunEngine + queueserver orchestration with its Conductor driving EPICS directly, or drives through the queueserver/httpserver as an actuation port leaving Bluesky in place (the lighter option). The choice is the central design question and likely generalizes across the migrated beamlines rather than going per-beamline. Pitch CORA on governance, replayability, and recipe-binding, never on out-executing Bluesky on scan speed.

**Source-of-truth contest (data).** The NATS JetStream document bus and the emerging Tiled/Redis store are the existing data-acquisition path; CORA brings its own data of record (PG event store), so these become a source to subsume, not a system CORA depends on. Defer the catalog decision (feed downstream vs project into) until a CLS deployment that must publish into a confirmed catalog is actually in scope.

**Coexist.** CLS scheduling / user-office identity (read, do not replace); reconstruction / analysis compute such as `sgmdata` and CT reconstruction for BMIT (a port roundtrip CORA governs but does not own); the archive (an egress destination); beamline data websites and logbooks (subsumed at the debrief layer, not competed with directly).

---

## 7. Open questions (for facility staff)

These could not be settled from public sources and need operator confirmation before any seam lock. Ask the CLS Beamline Controls / Scientific Computing group (named contact unknown).

1. **Orchestration boundary per beamline:** which beamlines still run in-house acquisition apps (the `pyStxm` class) and which have migrated to Bluesky RunEngine + queueserver, and where is the replace-vs-drive-through line? This bounds the ControlPort surface.
2. **Real device inventory / PV wiring:** the production PV namespace per beamline (SM's real prefixes behind the `SIM_IOC:` structure in `pyStxm`, and the full device lists for BMIT, BioXAS, HXMA, VESPERS, CMCF, and the rest) lives in deployment config not in public GitHub. What are the real handles?
3. **Fast paths:** which beamlines use EtherCAT / `ecmc` motion vs standard EPICS motor records, and where does hardware triggering / piezo-waveform fly-scanning (PI E-712) sit relative to the scan engine?
4. **Data catalog seam:** is there a facility-wide catalog (Tiled, SciCat, or other), is ingestion mandatory, and at what point in the run lifecycle does it trigger? Is NATS JetStream the production document bus facility-wide or per-deployment?
5. **Identity / scheduling chain:** the CLS user-office / proposal system and its role/permission model that CORA's Trust BC must read but not replace.
6. **Identifier mapping:** the authoritative mapping from beamline acronym (SM, BMIT-BM/ID) to internal sector.station code (SM = 10ID1) to run-context, so CORA's descriptor identifiers align with CLS conventions.
7. **Machine parameters:** confirmed ring circumference, emittance, current, and fill pattern from the CLS accelerator page (Wikipedia's 171 m is the only fetched figure).

---

## 8. Source list

**Facility (hardware facts):**
- CLS beamlines (roster + energies): https://www.lightsource.ca/facilities/beamlines/where-to-start.php
- CLS home: https://www.lightsource.ca/
- SGM beamline: https://sgm.lightsource.ca
- Wikipedia, Canadian Light Source (ring energy, circumference, EPICS, beamline count): https://en.wikipedia.org/wiki/Canadian_Light_Source

**Control system (software facts):**
- Canadian-Light-Source GitHub org: https://github.com/Canadian-Light-Source
- pyStxm (SM STXM acquisition app): https://github.com/Canadian-Light-Source/pyStxm
- bluesky-nats (document bus over NATS JetStream): https://github.com/Canadian-Light-Source/bluesky-nats
- bluesky-queueserver (fork of bluesky/bluesky-queueserver): https://github.com/Canadian-Light-Source/bluesky-queueserver
- ophyd-async (fork of bluesky/ophyd-async): https://github.com/Canadian-Light-Source/ophyd-async
- bluesky: https://github.com/Canadian-Light-Source/bluesky
- EPICS device-IO modules: xspress3 https://github.com/Canadian-Light-Source/xspress3 , pmac https://github.com/Canadian-Light-Source/pmac , motorSmarAct https://github.com/Canadian-Light-Source/motorSmarAct , motorXeryon https://github.com/Canadian-Light-Source/motorXeryon , StreamDevice https://github.com/Canadian-Light-Source/StreamDevice , ecmccfg https://github.com/Canadian-Light-Source/ecmccfg , ethercat https://github.com/Canadian-Light-Source/ethercat , PIE712MotorApp https://github.com/Canadian-Light-Source/PIE712MotorApp , require https://github.com/Canadian-Light-Source/require , ioc-rs https://github.com/Canadian-Light-Source/ioc-rs

**Data management:**
- sgmdata (SGM analysis helper): https://github.com/Canadian-Light-Source/sgmdata (data site https://sgm.lightsource.ca)
- kv-dict (Redis-backed dict): https://github.com/Canadian-Light-Source/kv-dict
- test-redis-ws (Tiled + Redis + WebSockets): https://github.com/Canadian-Light-Source/test-redis-ws

**Internal-only (named, not reachable):** the production per-beamline EPICS deployment configuration (real PV namespaces) and any facility-wide catalog / user-office system, referenced indirectly via `pyStxm`'s externalized config and the Tiled/Redis work-in-progress repos but not published.
