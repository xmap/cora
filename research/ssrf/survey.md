# SSRF (Shanghai Synchrotron Radiation Facility) research brief

*Research seed for a future CORA deployment page. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about SSRF, its beamline roster, and its control-software stack so the model work can begin from corroborated facts rather than memory. Every claim is cited inline. CORA is not connected to SSRF; the seam section is an initial read, not a commitment. Compiled 2026-07-01 from a deep-research web survey (facility pages, SINAP/Nuclear Science and Techniques papers, IUCr Journal of Synchrotron Radiation, JACoW proceedings, GitHub API). Web search was intermittently unavailable during the survey; most facts were gathered by direct fetch and via the DuckDuckGo HTML endpoint.*

!!! note "Reading posture"
    Public facility pages (`e-ssrf.sari.ac.cn`, `lssf.cas.cn`, Wikipedia) are the source of HARDWARE FACTS (ring energy, beamline IDs, techniques, energies, detectors). Public papers and proceedings (Nuclear Science and Techniques, IUCr, JACoW) are the source of CONTROL-SOFTWARE FACTS (what runs the scans, what talks to devices). Confidence is flagged inline as **[verified]** (multiple sources or a decisive primary), **[partly verified]**, or **[unconfirmed]**. Per CORA's deployment-doc lens, the facility software stack is named ONLY at the seam (section 6): it is the floor CORA lands on or the orchestration CORA replaces, never a spec CORA mirrors. SSRF publishes no per-beamline device configuration with real control handles (no SINAP/SSRF GitHub org exists; the beamline pages are descriptive HTML, not machine-readable config), so per-beamline device topology is routed to the staff questions (section 7), NOT inferred from shared frameworks. Inference is not source.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | Shanghai Synchrotron Radiation Facility (SSRF), third-generation medium-energy storage-ring light source | [Wikipedia](https://en.wikipedia.org/wiki/Shanghai_Synchrotron_Radiation_Facility), [CAS LSSF](https://lssf.cas.cn/en/facilities/material/ssrf/202505/t20250526_5070086.html) |
| Operator | Shanghai Advanced Research Institute (SARI) / Shanghai Institute of Applied Physics (SINAP), Chinese Academy of Sciences | [CAS LSSF](https://lssf.cas.cn/en/facilities/material/ssrf/202505/t20250526_5070086.html), [Wikipedia](https://en.wikipedia.org/wiki/Shanghai_Synchrotron_Radiation_Facility) |
| Location | Zhangjiang Hi-Tech Park, Pudong, Shanghai, China | [Wikipedia](https://en.wikipedia.org/wiki/Shanghai_Synchrotron_Radiation_Facility) |
| Ring energy | 3.5 GeV electron storage ring | [Wikipedia](https://en.wikipedia.org/wiki/Shanghai_Synchrotron_Radiation_Facility), [CAS LSSF](https://lssf.cas.cn/en/facilities/material/ssrf/202505/t20250526_5070086.html) |
| Circumference | 432 m | [Wikipedia](https://en.wikipedia.org/wiki/Shanghai_Synchrotron_Radiation_Facility) |
| Injector | 150 MeV linac + 3.5 GeV booster | [CAS LSSF](https://lssf.cas.cn/en/facilities/material/ssrf/202505/t20250526_5070086.html), [JACoW IPAC10 WEPEB009](https://proceedings.jacow.org/IPAC10/papers/wepeb009.pdf) |
| First user ops | May 2009; national acceptance Jan 2010 | [CAS LSSF](https://lssf.cas.cn/en/facilities/material/ssrf/202505/t20250526_5070086.html), [Wikipedia](https://en.wikipedia.org/wiki/Shanghai_Synchrotron_Radiation_Facility) |
| Phase-II Beamline Project | initiated 2016; passed national acceptance 2024 | [CAS LSSF](https://lssf.cas.cn/en/facilities/material/ssrf/202505/t20250526_5070086.html) |
| Beamlines open to users (2025) | 34 beamlines, 46 experimental stations | [CAS LSSF](https://lssf.cas.cn/en/facilities/material/ssrf/202505/t20250526_5070086.html) |

**[verified]** SSRF is a 3.5 GeV third-generation medium-energy storage ring (432 m circumference) in Shanghai's Zhangjiang district, operated by SARI/SINAP (CAS), open to users since 2009. Its Phase-II Beamline Project ran 2016 to 2024: the enabling proposal was for "18 new beamlines and more than 30 end-stations" over a six-year construction period ([IOP CS 2380 012004](https://iopscience.iop.org/article/10.1088/1742-6596/2380/1/012004)); by national acceptance the facility describes the completed project as delivering roughly "16 newly built beamlines with nearly 60 experimental methods" (facility text surfaced via search snippet, underlying page not re-fetched this pass; corroborated by the [LSSF](https://lssf.cas.cn/en/facilities/material/ssrf/202505/t20250526_5070086.html) 34-beamline/46-station figure). The 18-vs-16 gap is a proposal-vs-delivered snapshot difference to reconcile with staff (Q1). **[partly verified]**

The single most citable hook for CORA's data-of-record / debrief value proposition here is the **Big Data Science Center (BDSC)**, which SSRF describes as "the first Superfacility in China, and one of the first worldwide," fronted by the **SSRF-SciCat** metadata management system ([BDSC portal](https://bdsc.ssrf.ac.cn/en), [IUCr J. Synchrotron Rad. 2024](https://onlinelibrary.wiley.com/doi/full/10.1107/S1600577524007239), paywalled). A facility that already runs a SciCat-based metadata catalogue and an automated online-processing superfacility has made an explicit claim on part of the "system of record" territory CORA claims: this is the seam contest to sharpen, not a greenfield.

---

## 2. Candidate beamlines

**Source-of-record posture (decides Tier-2 buildability).** SSRF does **not** publish per-beamline device configuration with real control handles. There is no public SINAP / SSRF / SARI GitHub or GitLab organization (direct org lookups for `SINAP`/`SSRF` returned 404; the repo-search half was inconclusive: the unauthenticated code-search API returned an empty count, which is weaker evidence than a confirmed-empty result). The beamline pages under `e-ssrf.sari.ac.cn` and the CAS LSSF equipment catalogue are descriptive HTML (technique, energy, resolution), not machine-readable device config with EPICS PV prefixes. **[verified]** This places SSRF in the same posture as Sirius, SPring-8, and PSI's gitea: **a Tier-2 device pass is NOT buildable from public source.** The survey routes per-beamline device topology (PV namespaces, controller boxes, motion axes, detector wiring) to the staff questions in section 7. It is not inferred from the fact that beamlines share EPICS or CSS-BOY; a shared framework is not a device list.

Roster below is assembled from facility pages and per-beamline papers; every entry traces to a cited source. Energies and techniques are as published. Detectors are listed only where a source names them; blanks are "not found in public source," not "absent." Beamline IDs use the SSRF `BL<sector><letter><branch>` scheme (see identifier note).

| Beamline | ID | Technique | Energy | Detectors | Phase | Source |
| --- | --- | --- | --- | --- | --- | --- |
| X-ray Imaging & Biomedical (legacy) | BL13W1 | in-line phase-contrast imaging, micro-CT | (imaging) | | I | [NST 5270](https://www.nst.sinap.ac.cn/article/id/5270), [NST 10.1007/s41365-020-00805-7](https://link.springer.com/article/10.1007/s41365-020-00805-7) |
| X-ray Imaging & Biomedical (upgrade) | BL13HB | 2D/3D static & dynamic X-ray imaging, FOV up to 48.5 mm | 8-40 keV | | II (upgrade of BL13W1) | [NST 10.1007/s41365-023-01349-2](https://www.nst.sinap.ac.cn/article/doi/10.1007/s41365-023-01349-2) |
| Radioactive Materials / full-field imaging | BL13SSW | full-field X-ray imaging for radioactive materials, integrated control + DAQ | 5-50 keV | | II | [NST 10.1007/s41605-026-00692-3](https://link.springer.com/article/10.1007/s41605-026-00692-3), [NST 10.1007/s41365-026-01993-4](https://link.springer.com/article/10.1007/s41365-026-01993-4) |
| Hard X-ray Nanoprobe | BL13U | scanning nanoprobe, 50 to 10 nm spatial resolution, high-sensitivity detection | (hard X-ray) | | II | [NST 7116](https://www.nst.sinap.ac.cn/article/id/7116), [ADS 2024NuScT..35..121H](https://ui.adsabs.harvard.edu/abs/2024NuScT..35..121H/abstract) |
| XAFS | BL14W1 | X-ray absorption fine structure (XANES/EXAFS) | | | I | [e-ssrf BL14W1](https://e-ssrf.sari.ac.cn/beamlines/bl14w1/) |
| X-ray Diffraction | BL14B1 | X-ray diffraction | | | I | [e-ssrf BL14B1](https://e-ssrf.sari.ac.cn/beamlines/bl14b1/) |
| Hard X-ray Micro-Focusing | BL15U1 | micro-XRF, micro-XAS, micro-XRD; KB microprobe ~2 um, zone-plate <200 nm at 10 keV | 5-20 keV | | I | [CAS LSSF equipment](https://lssf.cas.cn/en/facilities/material/ssrf/equipment/202505/t20250527_5070175.html) |
| Soft X-ray Interference Lithography | BL08U1B | soft X-ray interference lithography | (soft X-ray) | | I | [e-ssrf beamline_maps bl08u1b](https://e-ssrf.sari.ac.cn/beamlines_2024/sr_72267/beamline_maps/bl08u1b/xzjs/) |
| Photoemission / ARPES ("Dreamline") | BL09U | X-ray photoemission spectroscopy & microscopy, ARPES | (soft X-ray) | I/II | [e-ssrf BL09U](https://e-ssrf.sari.ac.cn/beamlines/BL09U/) |
| Macromolecular Crystallography | BL02U1 | MX (relocated/upgraded, new ID) | 6-16 keV | | II | [NST 10.1007/s41365-023-01348-3](https://link.springer.com/article/10.1007/s41365-023-01348-3), [Finback PMC10914168](https://pmc.ncbi.nlm.nih.gov/articles/PMC10914168/) |
| Surface Diffraction | BL02U2 | surface & interface diffraction | ~10 keV | | II | [SciDB dataset](https://www.scidb.cn/en/detail?dataSetId=674edfb3401b4c36827d4b042848d33e) |
| Macromolecular Crystallography | BL10U2 | MX (Finback data collection) | | | II | [Finback PMC10914168](https://pmc.ncbi.nlm.nih.gov/articles/PMC10914168/), [RCSB BioSync](https://biosync.rcsb.org/beamlineprofile.do?synch_id=ssrf&region=Asian&bmln_name=BL10U2) |
| Time-resolved USAXS/SAXS/WAXS | BL10U1 | USAXS, SAXS, WAXS, microfocus-SAXS | | | II | [NST 10.1007/s41365-024-01389-2](https://link.springer.com/article/10.1007/s41365-024-01389-2) |
| BioSAXS | BL19U2 | biological-material small-angle X-ray scattering | | | I/II | [ResearchGate BL10U1/BL19U2](https://www.researchgate.net/publication/379520192) |
| Protein Micro-crystallography | BL18U1 | protein micro-crystallography | | | I/II | [e-ssrf beamline_maps bl18u1](https://e-ssrf.sari.ac.cn/beamlines_2024/sr_72267/beamline_maps/bl18u1/xzjs/) |
| MX (remote collection, legacy) | BL17U1 | MX; earlier Blu-Ice/DCS remote collection | | | I | [ScienceDirect S0168900218314815](https://www.sciencedirect.com/science/article/pii/S0168900218314815) |
| Energy Materials Research (soft branch) | BL20U2 | energy-materials research | (soft X-ray) | | II | [e-ssrf beamline_maps bl20u2](https://e-ssrf.sari.ac.cn/beamlines_2024/sr_72267/beamline_maps/bl20u2/xzjs/) |
| Ultra-hard X-ray multi-functional | BL12SW | high-energy X-ray diffraction & imaging | (ultra-hard) | | II | [e-ssrf beamline_maps bl12sw](https://e-ssrf.sari.ac.cn/beamlines_2024/sr_72267/beamline_maps/bl12sw/xzjs/) |

This is a partial roster (the facility runs 34 beamlines; the authoritative full Phase-II list is behind the paywalled [NST "Overview of SSRF phase-II beamlines"](https://link.springer.com/article/10.1007/s41365-024-01487-1), which could not be fetched). The tomography / imaging cluster (BL13HB, BL13SSW, BL13U nanoprobe) is the CORA-relevant set given the imaging/tomography pilot lean. **[partly verified]** as a complete enumeration; each listed beamline is individually **[verified]** against its cited source.

**Identifier-scheme note:** SSRF names beamlines `BL<sector><letter><branch>`, e.g. `BL13W1` (sector 13, wiggler, branch 1), `BL13U` (sector 13, undulator), `BL02U1` / `BL02U2` (sector 2, undulator, branches 1 and 2), `BL13SSW`, `BL12SW` (superconducting wiggler / special source). Endstation branches are encoded in the trailing digit. This differs from the APS `sector.station` (e.g. `2-BM`) scheme the pilot assumes: SSRF folds source-type (`W`/`U`/`B`/`SW`/`SSW`) and branch into one ID token, and beamlines can be **relocated and re-IDed** across a phase (the MX beamline was "relocated, upgraded, and given a new ID (BL02U1)"). CORA's descriptor identifier scheme must treat the beamline ID as a mutable label over a stable endstation, not a coordinate. This is a descriptor / identifier-scheme difference to model, not a hardware difference. **[verified]**

---

## 3. Control-system stack, by layer

SSRF is **EPICS-based** at both the accelerator and beamline levels. The accelerator control system is documented; the beamline experiment-control layer is documented per beamline in papers rather than in a public config repository.

### Device IO (the floor)

- **EPICS** is the control-system foundation. The accelerator control system is "a large hierarchical standard accelerator control system based on EPICS" running EPICS base 3.14.8.2, with VME 64x (GE VMIVME-7050, Motorola MV5500), PLCs (Yokogawa FA-M3, Siemens S300), MOXA serial-to-Ethernet translators, and soft IOCs on centralized PC rack servers ([JACoW IPAC10 WEPEB009](https://proceedings.jacow.org/IPAC10/papers/wepeb009.pdf), accelerator-side, 2010). **[partly verified: single 2010 primary; the hyper-specific model strings trace to this one PDF, which could not be re-fetched/re-read this pass, and are 15+ years stale for a live facility. Confirm with staff before a deployment page quotes them.]** The EPICS foundation is the load-bearing claim; the specific hardware models are dated and illustrative. The same EPICS foundation extends to beamlines per the beamline papers below.
- **Beamline device IO is EPICS.** Beamline control and data-acquisition software "are developed using EPICS in Linux," with Python for complex control logic, over a VME/IOC platform with ADC/DAC modules covering motion control, detector control, and scan mechanisms ([BL13SSW integrated control paper, DuckDuckGo-surfaced abstract](https://link.springer.com/article/10.1007/s41605-026-00692-3)). **[partly verified]** (single decisive source per beamline; not aggregated across the fleet). This is below CORA's seam; CORA's ControlPort would drive through it, never own it.
- The accelerator machine-protection system (MPS) is a Yokogawa FA-M3R PLC layer with EPICS for monitoring via NetDev; insertion-device local control is Siemens PLC with an embedded MontaVista-Linux EPICS controller for the upper layer ([JACoW IPAC10 WEPEB009](https://proceedings.jacow.org/IPAC10/papers/wepeb009.pdf)). The accelerator-side EPICS stack is out of CORA's scope. **[verified]**

### Scan orchestration (the seam layer)

- There is **no facility-wide bluesky / queueserver layer** evident in public source (an absence, not a positive finding: no SSRF beamline-control source names Bluesky). Note that **Mamba** (the Bluesky-based experiment-control framework) is developed for **HEPS (High Energy Photon Source), NOT SSRF** ([Mamba paper, arXiv:2203.17236](https://arxiv.org/abs/2203.17236)); it must not be attributed to SSRF. **[partly verified: the Mamba-is-HEPS-not-SSRF fact is verified; the SSRF-has-no-Bluesky claim is an absence-of-evidence over public source, not a confirmed absence.]**
- The scan / experiment-control layer at SSRF is **per-beamline EPICS-based software with a CSS-BOY GUI** and Python control logic (the BL13SSW integrated-control paper states "the graphical user interface (GUI) is based on CSS-BOY", [Springer s41605-026-00692-3](https://link.springer.com/article/10.1007/s41605-026-00692-3); surfaced via search snippet, full text not read this pass). **[partly verified]** This is the layer CORA's EdgeConductor would conduct over, incrementally and routine-by-routine. Because it appears home-grown per beamline rather than a single facility framework, the replace-vs-drive-through decision may be per-beamline rather than facility-uniform (the opposite of Sirius's uniform sophys).
- **MX beamlines** run **Finback**, an in-house integrated software system for MX data collection, deployed at BL02U1 and BL10U2 since June 2021: "The backend is based on the Experimental Physics and Industrial Control System [EPICS] and the frontend has been developed with ... WebSocket, WebGL, WebWorker and WebAssembly" ([Finback, PMC10914168](https://pmc.ncbi.nlm.nih.gov/articles/PMC10914168/)). An earlier remote-collection system at BL17U1 used a **Blu-Ice/DCS** architecture ([ScienceDirect S0168900218314815](https://www.sciencedirect.com/science/article/pii/S0168900218314815)). **[verified]**

### Fast paths and exceptions

- Accelerator-side digital subsystems (digital power-supply controllers, digital BPM, digital timing with hardware timestamp, a new FPGA-based fast-interlock controller) sit on EPICS but use dedicated digital links ([JACoW IPAC10 WEPEB009](https://proceedings.jacow.org/IPAC10/papers/wepeb009.pdf)). These are accelerator-domain and out of CORA's beamline scope. **[verified]**
- Whether beamline fly-scans use a direct hardware-trigger path (PandABox-style) below EPICS, or a facility-standard detector DAQ backend, is **not** settled in public source. **[unconfirmed]** (staff question).

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| `e-ssrf.sari.ac.cn` | facility + per-beamline descriptive pages (HTML), user portal, BDSC entry | [e-ssrf](https://e-ssrf.sari.ac.cn/) (TLS / 403 issues on direct fetch) |
| `bdsc.ssrf.ac.cn` | Big Data Science Center portal (SSRF-SciCat, superfacility) | [BDSC](https://bdsc.ssrf.ac.cn/en) |
| `lssf.cas.cn` | CAS Large-Scale Scientific Facilities catalogue (SSRF equipment listing) | [CAS LSSF](https://lssf.cas.cn/en/facilities/material/ssrf/202505/t20250526_5070086.html) |
| Nuclear Science and Techniques (`nst.sinap.ac.cn` / Springer) | per-beamline design/commissioning papers (the de-facto device documentation) | [NST journal](https://www.nst.sinap.ac.cn/) (TLS mismatch on direct fetch; Springer paywalled) |

**Why a full device model is NOT integrity-buildable from public source.** SSRF publishes **no** per-beamline device configuration with real control handles: no public SINAP/SSRF/SARI code organization exists on GitHub or GitLab (direct org lookups returned 404; the unauthenticated repo-search was inconclusive rather than confirmed-empty), and the beamline pages are prose descriptions, not IOC / substitution files / device databases. The per-beamline device inventory (EPICS PV namespaces, motor controller models, detector wiring, axis groupings) lives inside the facility network and in the paywalled NST design papers. A Tier-2 device pass would therefore fabricate PVs if attempted from public source; it is **not buildable** and the device topology is routed to staff questions. This matches the Sirius / SPring-8 firewalled posture. **[verified]**

---

## 5. Data management

SSRF has an unusually mature, named data-of-record stack, which sharpens the seam contest:

- **BDSC (Big Data Science Center):** SSRF describes it as "the first Superfacility in China, and one of the first worldwide" ([e-ssrf BDSC](http://e-ssrf.sari.ac.cn/for_users/bdsc/), [BDSC portal](https://bdsc.ssrf.ac.cn/en)). It provides HPC resources and automated online processing / real-time feedback for beamline data ([IUCr J. Synchrotron Rad. 2024](https://onlinelibrary.wiley.com/doi/full/10.1107/S1600577524007239), paywalled). **[partly verified: decisive source paywalled]**
- **SSRF-SciCat:** the facility's metadata management system, a deployment of the ESRF/PSI-lineage **SciCat** catalogue, "collecting, tagging and tracking large volumes of metadata from all the experiments at SSRF" ([BDSC news](https://bdsc.ssrf.ac.cn/en/ssrf/achievements/news/1689471723116613634.html)). The BDSC SR-CT (tomography) reconstruction framework "fully utilizes the SSRF-SciCat metadata management system" ([IUCr J. Synchrotron Rad. 2024](https://onlinelibrary.wiley.com/doi/full/10.1107/S1600577524007239), **paywalled: HTTP 402, not readable this pass**). The SSRF-SciCat existence is **[verified]** via the BDSC portal/news; the SR-CT-fully-utilizes-SciCat linkage rests on the unreadable paywalled paper and is **[partly verified]**.
- **Formats:** HDF5 / NeXus is the working direction for imaging beamlines, consistent with the SR-CT framework and SciCat integration ([IUCr J. Synchrotron Rad. 2024](https://onlinelibrary.wiley.com/doi/full/10.1107/S1600577524007239), paywalled). The exact NeXus application definitions written per beamline (e.g. NXtomo) are **not** established in public source. **[partly verified]**
- **Ingestion trigger:** at what point acquisition data is registered into SSRF-SciCat (per-scan, per-proposal, on-completion), and whether ingestion is mandatory, is **not** established publicly. **[unconfirmed]** (staff question).

This is a direct source-of-truth contest: SSRF-SciCat already claims the metadata-catalogue-of-record role, and BDSC claims the online-processing role. CORA's data-of-record posture ("we do our own event store") must be positioned against an existing, named catalogue here, not into a vacuum.

---

## 6. The CORA seam (initial read)

First pass, not a committed seam. Applies the 2-BM / FXI lens: device IO is the floor CORA never replaces; the higher scan / orchestration layer is where CORA replaces or drives through; the facility catalogue is a source-of-truth contest, not a dependency.

**Where the floor stays the floor (drive through, never CORA).** SSRF beamline device IO is EPICS (VME/soft IOCs, PLCs, MOXA serial bridges), the same substrate as the APS 2-BM pilot. CORA's ControlPort model carries over: CORA actuates **through** the EPICS floor and never owns PVs, IOCs, or the device layer. No new control substrate needs building. The one caveat is that the per-beamline PV namespace is not public, so the ControlPort surface can only be pinned per beamline with staff input (section 7). **[partly verified]**

**What CORA replaces (edge orchestration).** The scan / experiment-control layer is per-beamline EPICS + CSS-BOY + Python software (and Finback for MX), not a single facility framework. CORA's EdgeConductor would conduct routines over the EPICS floor where this per-beamline software sits today, incrementally and routine-by-routine. Treat the existing per-beamline software (and Finback) as DATA to learn from, never a spec to mirror: Finback in particular is a solid, modern, in-production MX system, so the CORA pitch is governance, replayability, and recipe-binding, NOT out-executing Finback on MX throughput. Because orchestration is per-beamline rather than uniform, the replace-vs-drive-through boundary likely differs per beamline (unlike Sirius's facility-wide sophys), which raises the modeling cost and makes the imaging cluster (home-grown scan software, closest to the pilot) the cleaner entry point than MX (Finback, already excellent).

**Source-of-truth contest (data).** SSRF-SciCat (metadata catalogue) and BDSC (superfacility online processing + HPC) are the existing data-of-record and compute layers. CORA stays the system of record for the experiment; SSRF-SciCat is named only at the seam, either inverted (fed downstream from CORA's event store) or projected into. This is a live contest, not a deferred abstraction, because the catalogue is real, named, and facility-wide. Defer the actual decision until a deployment running SSRF-SciCat is in scope, but flag it as the sharpest catalogue contest in the fleet so far.

**Coexist.** BDSC HPC / SR-CT reconstruction is a compute port roundtrip CORA governs but does not own (a ComputePort target). The user-office / proposal and identity chain (unknown system) is read, not replaced. The archive is an egress destination. Any per-beamline electronic logbook is subsumed at CORA's debrief layer.

---

## 7. Open questions (for facility staff)

These could not be settled from public sources and need operator confirmation before any seam lock. The device-topology questions exist because SSRF publishes no per-beamline device config (section 4); they are not gaps to invent around.

1. **Beamline roster and Phase-II reconciliation:** the authoritative full list of the 34 operating beamlines and their Phase-II vs Phase-I status, and the 18-proposed / 16-delivered reconciliation. Which beamlines are the imaging/tomography cluster (BL13HB, BL13SSW, BL13U nanoprobe) and their current calibrated energy ranges and detectors?
2. **Per-beamline device inventory (firewalled):** EPICS PV namespaces, motor controller models, detector wiring, axis groupings per beamline. This bounds the ControlPort surface and is entirely non-public.
3. **Scan-orchestration boundary per beamline:** for the imaging beamlines, is the scan engine home-grown EPICS+CSS-BOY+Python, and what is the replace-vs-drive-through boundary CORA's EdgeConductor should target? Is there any facility-standard scan framework, or is each beamline independent?
4. **Fast paths:** do fly-scans use a hardware-trigger path (e.g. PandABox / FPGA timing) below EPICS, or a facility-standard detector DAQ backend that widens the ControlPort surface?
5. **SSRF-SciCat ingestion seam:** is ingestion into SSRF-SciCat mandatory, and at what point (per-scan, on-completion, per-proposal)? What NeXus application definitions (NXtomo?) are written, and where does raw data land relative to BDSC storage?
6. **BDSC compute seam:** is reconstruction expected inline with acquisition (real-time feedback), and how would a CORA ComputePort roundtrip map onto BDSC's SLURM/superfacility model?
7. **Identity / proposal / governance:** the user-office/proposal system, the role/permission model, and any per-beamline logbook, for the Trust/governance seam.
8. **MX exception:** for BL02U1/BL10U2 (Finback) and BL18U1, is CORA in scope at all, or is Finback the settled MX solution and CORA's entry limited to imaging/spectroscopy beamlines?

---

## 8. Source list

**Facility (hardware facts):**
- Wikipedia, Shanghai Synchrotron Radiation Facility: https://en.wikipedia.org/wiki/Shanghai_Synchrotron_Radiation_Facility
- CAS LSSF, SSRF (incl. Phase-II): https://lssf.cas.cn/en/facilities/material/ssrf/202505/t20250526_5070086.html
- CAS LSSF, SSRF equipment (BL15U1 etc.): https://lssf.cas.cn/en/facilities/material/ssrf/equipment/202505/t20250527_5070175.html
- SSRF user portal / beamline maps: https://e-ssrf.sari.ac.cn/ (TLS / 403 on direct fetch; slugs surfaced via search)
- BL09U (Dreamline): https://e-ssrf.sari.ac.cn/beamlines/BL09U/
- BL14W1 (XAFS): https://e-ssrf.sari.ac.cn/beamlines/bl14w1/
- BL14B1 (XRD): https://e-ssrf.sari.ac.cn/beamlines/bl14b1/
- RCSB BioSync, SSRF BL10U2: https://biosync.rcsb.org/beamlineprofile.do?synch_id=ssrf&region=Asian&bmln_name=BL10U2

**Beamline design / commissioning papers (device documentation surrogate):**
- Overview of SSRF Phase-II beamlines (paywalled): https://link.springer.com/article/10.1007/s41365-024-01487-1
- Commissioning & First Results of SSRF Phase-II Beamline Project (IOP CS 2380): https://iopscience.iop.org/article/10.1088/1742-6596/2380/1/012004
- BL13U hard X-ray nanoprobe (NST): https://www.nst.sinap.ac.cn/article/id/7116 / https://ui.adsabs.harvard.edu/abs/2024NuScT..35..121H/abstract
- BL13HB X-ray imaging & biomedical (NST): https://www.nst.sinap.ac.cn/article/doi/10.1007/s41365-023-01349-2
- BL13W1 imaging (NST): https://www.nst.sinap.ac.cn/article/id/5270 / https://link.springer.com/article/10.1007/s41365-020-00805-7
- BL13SSW radioactive-materials imaging + integrated control/DAQ: https://link.springer.com/article/10.1007/s41605-026-00692-3 / https://link.springer.com/article/10.1007/s41365-026-01993-4
- BL02U1 MX (NST): https://link.springer.com/article/10.1007/s41365-023-01348-3
- BL10U1 time-resolved USAXS/SAXS/WAXS (NST): https://link.springer.com/article/10.1007/s41365-024-01389-2
- Status of MX beamlines at SSRF (IUCr): https://journals.iucr.org/s/issues/2025/01/00/he5681/

**Control software (software facts):**
- THE SSRF CONTROL SYSTEM (JACoW IPAC10 WEPEB009, accelerator EPICS): https://proceedings.jacow.org/IPAC10/papers/wepeb009.pdf
- Finback web-based MX data collection (backend EPICS): https://pmc.ncbi.nlm.nih.gov/articles/PMC10914168/ / https://journals.iucr.org/s/issues/2024/02/00/wz5035/wz5035.pdf
- BL17U1 remote MX collection (Blu-Ice/DCS): https://www.sciencedirect.com/science/article/pii/S0168900218314815
- Mamba (HEPS, NOT SSRF; disambiguation): https://arxiv.org/abs/2203.17236 / https://doi.org/10.1107/S1600577522002697
- EPICS Controls SSRF project page: https://epics-controls.org/projects-archive/ssrf/

**Data management:**
- BDSC portal: https://bdsc.ssrf.ac.cn/en / http://e-ssrf.sari.ac.cn/for_users/bdsc/
- SSRF-SciCat metadata (BDSC news): https://bdsc.ssrf.ac.cn/en/ssrf/achievements/news/1689471723116613634.html
- Accelerating imaging research at large-scale facilities (SSRF-SciCat + BDSC SR-CT, IUCr J. Synchrotron Rad. 2024) (paywalled, HTTP 402): https://onlinelibrary.wiley.com/doi/full/10.1107/S1600577524007239
- BDSC online beamline data processing (IUCr): https://journals.iucr.org/s/issues/2024/05/00/ju5063/
- Deploying the Big Data Science Center at SSRF (IOP MLST): https://iopscience.iop.org/article/10.1088/2632-2153/abe193

**Internal-only / not publicly resolvable:** SSRF facility network device configuration (EPICS IOC databases, PV namespaces); the paywalled NST "Overview of SSRF phase-II beamlines" (authoritative full roster); no public SINAP/SSRF/SARI code VCS org found on GitHub or GitLab.
