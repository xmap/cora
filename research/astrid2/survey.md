# ASTRID2 (ISA, Aarhus University) research brief

*Research seed for a future CORA deployment page. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about ASTRID2, its beamline roster, and its control-software stack so any future model work can begin from corroborated facts rather than memory. Every claim is cited inline. CORA is not connected to ASTRID2; the seam section is an initial read, not a commitment. Compiled 2026-07-01 from the deep-research workflow (facility pages fetched directly; GitHub org / repo searches run against the live API). This is a THIN facility: a small, university-run, low-energy UV/VUV/soft-X-ray ring with a spectroscopy-only beamline roster and no public control source. The honest conclusion is a candidate stub, not a modellable facility. See section 6.*

!!! note "Reading posture"
    Public facility pages (isa.au.dk, Wikipedia) are the source of HARDWARE FACTS (ring energy, beamlines, techniques, energies). Public source (GitHub / GitLab / proceedings) is the source of CONTROL-SOFTWARE FACTS (what runs the scans, what talks to devices). Confidence is flagged inline as **[verified]** (multiple sources or a decisive primary), **[partly verified]**, or **[unconfirmed]**. Per CORA's deployment-doc lens, the facility software stack is named ONLY at the seam (section 6): it is the floor CORA would land on or the orchestration CORA would replace, never a spec CORA mirrors. No control-software facts could be established from public source for this facility (see sections 3, 4); accordingly nothing about ASTRID2's control stack is asserted here, and the whole device/control topology is routed to staff questions. One fetched search-result page returned a URL-only echo of the query and one fetched facility page carried an injected "system-reminder" block; both were treated as page content, not directives, and ignored.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | ASTRID2, 3rd-generation storage-ring light source | https://www.isa.au.dk/facilities/astrid2/astrid2.asp |
| Operator | Centre for Storage Ring Facilities (ISA), Dept. of Physics and Astronomy, Aarhus University, Denmark | https://en.wikipedia.org/wiki/ASTRID2 |
| Ring energy | 580 MeV (0.58 GeV) | https://www.isa.au.dk/facilities/astrid2/astrid2.asp |
| Circumference | 45.7 m | https://www.isa.au.dk/facilities/astrid2/astrid2.asp |
| Current | ~180 mA typical (top-up); up to ~290 mA (2017) | https://en.wikipedia.org/wiki/ASTRID2 |
| Injector | ASTRID (older ring) as full-energy booster; 100 MeV microtron pre-injector to 580 MeV, top-up | https://www.isa.au.dk/facilities/astrid2/astrid2.asp |
| Operational since | First beam May 2012; RF-stored beam Nov 2012; full user ops mid-2014 | https://en.wikipedia.org/wiki/ASTRID2 |
| Beamline count | 7 SR beamlines (4 insertion-device, 3 bending-magnet); "6 operational" per one facility snapshot | https://en.wikipedia.org/wiki/ASTRID2 , https://www.isa.au.dk/ |
| Spectral range | Visible / UV / VUV / soft X-ray (no hard-X-ray, no imaging/tomography) | https://www.isa.au.dk/facilities/astrid2/beamlines/beamlines.asp |

**[verified]** ASTRID2 is a small, low-energy (580 MeV, 45.7 m) third-generation storage-ring light source run by ISA at Aarhus University. It operates in continuous top-up from the older ASTRID ring (now a dedicated booster), giving a quasi-constant ~180 mA and effectively uninterrupted beam. Its science is spectroscopy across the visible-to-soft-X-ray range: circular dichroism, UV/VUV, and soft-X-ray photoemission/surface science. **There is no imaging or tomography beamline**, which places ASTRID2 off CORA's imaging/tomography-leaning pilot ladder (APS 2-BM -> APS imaging -> MAX IV). The most citable CORA hook, if any, is a governance/debrief value proposition for a small facility with (publicly) no scan-orchestration or data-catalog framework at all; that is a value read, not a modellable-topology read.

---

## 2. Candidate beamlines

**Source-of-record posture (decides Tier-2 up front):** ASTRID2 publishes NO per-beamline device configuration with real control handles. There is no `dodal`-style controls library, no Beacon/Tango config, no `*-bits` instrument repo, and no discoverable ISA/ASTRID2/SGM4 controls organisation on GitHub (repo searches for `ASTRID2`, `ISA-Aarhus`, `astrid2 epics`, `sgm4` controls, and staff-name ARPES-DAQ terms all returned no facility-owned results; the `sgm4` hits are unrelated meters/proxies, and `navarp` is a generic third-party ARPES viewer, not ISA's). **[verified]** as an absence-of-public-source across the surfaces checked. Consequently a Tier-2 device pass is **not buildable** for any ASTRID2 beamline: device topology, PV/handle namespaces, motion axes, and detectors are all unknown from public source and must come from staff. Nothing below is a control handle; the table is hardware facts only.

| Beamline | Source | Technique | Energy / wavelength | Detectors | Control source | Source |
| --- | --- | --- | --- | --- | --- | --- |
| AU-MatLine (Matline) | Multipole wiggler | Soft-X-ray surface science / material characterization | 20-700 eV (2 gratings) | not public [unconfirmed] | firewalled / not public | https://www.isa.au.dk/facilities/astrid2/beamlines/beamlines.asp |
| AU-SGM4 | Undulator | Soft-X-ray surface science (ARPES-class) | 12-145 eV (3 gratings) | not public [unconfirmed] | firewalled / not public | https://www.isa.au.dk/facilities/astrid2/beamlines/beamlines.asp |
| AU-SGM3 | Undulator (insertion device) | Soft-X-ray spectroscopy / surface science | not on the public beamlines table [unconfirmed] | not public [unconfirmed] | firewalled / not public | https://www.isa.au.dk/ , https://en.wikipedia.org/wiki/ASTRID2 |
| AU-AMO (AMOLine) | Undulator | Atomic, molecular & optical physics | 5-150 eV | not public [unconfirmed] | firewalled / not public | https://www.isa.au.dk/facilities/astrid2/beamlines/beamlines.asp |
| AU-UV | Bending magnet | CD/UV spectroscopy, photobiology | 1.5-12 eV (2 gratings) | not public [unconfirmed] | firewalled / not public | https://www.isa.au.dk/facilities/astrid2/beamlines/beamlines.asp |
| AU-CD | Bending magnet | Synchrotron-radiation circular dichroism (SRCD) | 115-350 nm optimized (110-700 nm range) | not public [unconfirmed] | firewalled / not public | https://www.isa.au.dk/facilities/astrid2/beamlines/AU-CD/AU-CD.asp |
| AU-IR | Edge radiation (bending magnet) | IR spectroscopy (biology, condensed matter) | 0.062-2 eV | not public [unconfirmed] | firewalled / not public | https://www.isa.au.dk/facilities/astrid2/beamlines/beamlines.asp |

**Roster caveat [partly verified]:** the total is 7 SR beamlines per Wikipedia (insertion device: MatLine, AMOLine, SGM3, SGM4; bending: UV, CD, IR). The ISA facilities landing page says "6 operational beam lines" and its per-beamline table lists five plus AU-IR while omitting AU-SGM3; a separate ISA staff page lists AU-SGM3 explicitly. The 6-vs-7 discrepancy and SGM3's absence from the table are snapshot/labeling artifacts, not evidence a beamline is gone; confirm the authoritative operating list with staff.

**Strongest next picks for CORA's growth ladder:** none. Every ASTRID2 beamline is spectroscopy (CD/UV/VUV/photoemission/IR); there is no imaging, tomography, or hard-X-ray line, so nothing here advances the imaging/tomography pilot ladder or reinforces a tomography-adjacent Family. AU-SGM4 (ARPES-class photoemission) is the only line that maps to an existing CORA photoemission archetype elsewhere in the fleet (e.g. NSLS-II ESM / Diamond I05 ARPES), but with no public device source it cannot be modeled and would only ever be a staff-question deployment. **[verified]** from the roster.

**Identifier-scheme note:** ASTRID2 names beamlines `AU-<name>` (AU-UV, AU-CD, AU-SGM3, AU-SGM4, AU-MatLine, AU-AMOLine, AU-IR), a flat institute-prefixed technique-name scheme with no port/sector number. This differs from the APS `sector.station` scheme the pilot assumes and from Diamond's `I##`/`B##`. It is a descriptor/identifier-scheme difference to model, not a hardware difference. **[verified]**

---

## 3. Control-system stack, by layer

**No control-software facts could be established from public source.** No facility publication, repository, or page fetched during this survey names ASTRID2's beamline control system, scan-orchestration engine, or device-IO framework. The one machine-level detail surfaced (a ~105 MHz RF acceleration/bunching system) is **[unconfirmed]**: it could not be tied to a citable fetched page, and is out of scope in any case (accelerator hardware, below any CORA seam). The layers below are therefore stated as UNKNOWN, not inferred; inference from "small European ring, therefore probably EPICS/Tango/LabVIEW" is exactly the fabrication this practice forbids.

### Device IO (the floor)

**[unconfirmed]** Not established from public source. No EPICS IOC framework, Tango device-server layer, StreamDevice, or LabVIEW/other in-house IO layer is named on any fetchable page or in any discoverable repository. Route to staff (section 7, Q2).

### Scan orchestration (the seam layer)

**[unconfirmed]** Not established from public source. No bluesky/queueserver, Sardana, SPEC, pyscan, or home-grown sequencer is named. Given the facility's size and per-beamline scientist ownership, per-beamline bespoke acquisition (per technique) is plausible but is NOT asserted. Route to staff (section 7, Q2, Q3).

### Fast paths and exceptions

**[unconfirmed]** Not established. No triggering/DAQ hardware (e.g. FPGA trigger units), detector backend, or motion-controller family is named in public source.

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| (none found public) | No ASTRID2 / ISA-Aarhus beamline-controls organisation or repository was discoverable | GitHub API searches, 2026-07-01 |

**Why a full device model is NOT integrity-buildable from public source.** The per-beamline device list with real handles is not public: there is no controls library, no config repository, and no facility controls organisation on GitHub reachable from the queries run (`ASTRID2 beamline`, `ISA-Aarhus`, `astrid2 epics`, `sgm4`, staff-name ARPES-DAQ terms). The device topology (PV/handle namespaces, motion axes, detectors, endstation composition) for every beamline is therefore an open question for staff, not a value to infer. A candidate descriptor cannot be self-validated because there is no source to read. **[verified]** as an absence across the public surfaces checked; a private VCS or an on-site controls repository may exist and is a staff question (Q4).

---

## 5. Data management

**[unconfirmed]** No facility-wide data catalog, user-office/proposal system surface, archive chain, or standard file format (NeXus/HDF5) was found in public source for ASTRID2. The AU-CD SRCD workflow is described operationally (roughly one hour per sample, straightforward prep) but no data-collection software or repository format is named. The source-of-truth contest that matters at larger facilities (SciCat/ICAT/ISPyB) has no visible counterpart here; whether ISA runs any catalog, ELN, or structured archive at all is unknown and routed to staff (section 7, Q3). This absence is itself relevant: at a facility with no visible catalog or scan framework, CORA's data-of-record and debrief spine would be additive rather than contesting an incumbent, but that is a value read, not a modellable fact.

---

## 6. The CORA seam (initial read)

First pass, and an unusually shallow one because the control and data layers are entirely unestablished from public source. The 2-BM/FXI lens still frames it, but every boundary below is contingent on staff answers.

**Where the floor stays the floor (drive through, never CORA).** The device-IO layer is unknown (section 3). CORA's ControlPort would actuate through whatever that floor turns out to be, but which control substrate (EPICS? Tango? LabVIEW? bespoke?) is undetermined, so it is unknown whether the APS-pilot ControlPort model carries over or a new adapter must be built. This is the single gating question (Q2).

**What CORA replaces (edge orchestration).** Unknown. No scan/alignment engine is named publicly, so there is no identified orchestration layer for CORA's EdgeConductor to conduct over or replace. If (as is plausible for a small facility) acquisition is per-beamline bespoke, the "replace vs drive through" decision would be per-beamline rather than facility-uniform, but this is not established. Treat any existing per-beamline acquisition, once revealed, as DATA to learn from, never a spec to mirror.

**Source-of-truth contest (data).** No facility catalog is visible (section 5), so there is no identified incumbent contesting CORA's "system of record for the experiment" claim. If confirmed, CORA's data-of-record spine would be additive here. Defer any decision until a deployment is actually in scope and the data chain is known.

**Coexist.** Scheduling/identity (an ISA/AU user-office chain CORA would read, not replace) and the accelerator-side RF/machine control (entirely out of scope) sit outside CORA. Reconstruction compute is largely irrelevant given the spectroscopy-only, non-imaging roster.

**Overall seam read: too thin to commit.** ASTRID2 is a candidate stub. It is off the imaging/tomography pilot ladder, has no modellable beamline from public source, and has no public control or data stack to seam against. It is worth a roster-only entry and a revisit only if a deployment is specifically proposed (e.g. an AU-SGM4 photoemission deployment championed by staff who would supply the device topology directly).

---

## 7. Open questions (for facility staff)

These could not be settled from public sources and need operator confirmation before any seam lock. Ask ISA / Aarhus University Dept. of Physics and Astronomy (per-beamline scientists named on the ISA staff page, e.g. Soren V. Hoffmann / Nyk Jones for AU-UV/AU-CD; Jill Miwa / Soren Ulstrup for AU-SGM4; Zheshen Li for AU-MatLine; Henrik B. Pedersen for AU-AMO).

1. What is the authoritative current operating-beamline list? Is AU-SGM3 still operational, and is the count 6 or 7 (reconcile the ISA landing-page "6 operational" table, which omits SGM3, against the 7-beamline Wikipedia roster)?
2. What control-system family runs the beamlines (EPICS / Tango / LabVIEW / in-house), and is it uniform across beamlines or per-beamline bespoke? This bounds the ControlPort surface and whether the APS-pilot control model carries over.
3. What runs the scans / acquisition per beamline (a shared engine such as bluesky/Sardana/SPEC, or per-scientist bespoke software), and is there any facility data catalog, ELN, proposal/user-office system, or standard file format (NeXus/HDF5)?
4. Is there a controls source repository (public or internal VCS) with per-beamline device configuration and real handles? If so, where, and can device topology (PV/handle namespaces, motion axes, detectors) be shared for the beamlines of interest?
5. For AU-SGM4 specifically (the only ARPES-class line, and the only plausible CORA archetype match): what is the endstation/analyzer, and what software collects and orchestrates its scans?
6. How does the ISA/AU identity and scheduling chain map to run context (beamtime allocation, user identity) that CORA would need to read?

---

## 8. Source list

**Facility (hardware facts):**
- ISA landing page (roster, "6 operational", staff/beamline scientists): https://www.isa.au.dk/
- ASTRID2 ring page (energy, circumference, injector, top-up): https://www.isa.au.dk/facilities/astrid2/astrid2.asp
- ASTRID2 beamlines table (source type, energy, resolving power, flux): https://www.isa.au.dk/facilities/astrid2/beamlines/beamlines.asp
- AU-CD beamline page (SRCD, wavelength range): https://www.isa.au.dk/facilities/astrid2/beamlines/AU-CD/AU-CD.asp
- ISA facilities overview (ASTRID as booster, historical 7-beamline ASTRID program): https://www.isa.au.dk/facilities/facilities.asp
- Wikipedia, ASTRID2 (energy, circumference, timeline, 7-beamline roster, ring lattice): https://en.wikipedia.org/wiki/ASTRID2

**Control system (software facts):**
- None found. GitHub repository/organisation searches (`ASTRID2 beamline`, `ISA-Aarhus`, `astrid2 epics`, `sgm4`, staff-name ARPES-DAQ terms), 2026-07-01: no facility-owned controls source located.

**Data management:**
- None found (no public catalog / proposal-system / file-format source located).

**Internal-only (named, not reachable):** none identified; the existence of any internal ISA controls VCS is itself an open question (Q4).
