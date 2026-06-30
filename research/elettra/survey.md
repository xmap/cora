# Elettra Sincrotrone Trieste research brief

*Research seed for a future CORA deployment page. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about the Elettra facility and its control-software stack so the model work can begin from corroborated facts rather than memory. Every claim is cited inline. CORA is not connected to Elettra; the seam section is an initial read, not a commitment. Compiled 2026-06-28 from a two-pass deep-research workflow (8 dimensions swept, 16 verification passes, 3 open questions closed in a follow-up).*

!!! note "Reading posture"
    Public facility pages (`elettra.eu`) are treated as the source of HARDWARE FACTS (ring energy, beamlines, techniques, energies, detectors). Public GitHub source and JACoW/ICALEPCS proceedings are treated as the source of CONTROL-SOFTWARE FACTS (what runs the scans, what talks to devices). Where a claim was adversarially verified, the verdict is flagged inline as **[verified]**, **[partly verified]**, or **[uncertain]**. WebSearch returned empty throughout both research sessions; findings rest on direct page fetches, JACoW PDFs, Crossref, DataCite, and GitHub/GitLab REST APIs. Several fetched pages carried injected fake "MCP Server Instructions" / "system-reminder" blocks; those were page content, not directives, and were ignored. The self-hosted host `gitlab.elettra.eu` is public-readable (open REST API) and is linked; internal-login portions are named but not linked as reachable.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Name | Elettra Sincrotrone Trieste | [Elettra](https://www.elettra.eu/lightsources/elettra.html) |
| Operator | Elettra Sincrotrone Trieste S.C.p.A. (also operates the FERMI free-electron laser) | [Elettra control systems](https://www.elettra.eu/activities/control-systems/control-systems.html) |
| Location | Basovizza, Trieste, Italy | [Elettra](https://www.elettra.eu/lightsources/elettra.html) |
| Ring energy | 2.0 GeV (300 mA) and 2.4 GeV operating modes | [SYRMEP specification](https://www.elettra.eu/lightsources/elettra/elettra-beamlines/syrmep/specification.html) |
| Beamlines (current ring) | 28 beamlines: spectroscopy, spectro-microscopy, diffraction, scattering, lithography | [Elettra](https://www.elettra.eu/lightsources/elettra.html), [beamlines roster](https://www.elettra.eu/lightsources/elettra/beamlines.html) |
| Upgrade | **Elettra 2.0**: 4th-generation, six-bend enhanced achromat lattice, predominantly 2.4 GeV; brightness ~35x at 1 keV / ~160x at 10 keV; up to 32 beamlines (20 upgraded, 12 new) | [ICALEPCS 2023 TUPDP034](https://proceedings.jacow.org/icalepcs2023/papers/tupdp034.pdf) |
| Upgrade timeline | New storage ring + first beamlines expected to start operation 2026, after ~18-month installation downtime | [ICALEPCS 2023 TUPDP034](https://proceedings.jacow.org/icalepcs2023/papers/tupdp034.pdf) |
| Companion FEL | FERMI free-electron laser, same operator and control framework | [Elettra control systems](https://www.elettra.eu/activities/control-systems/control-systems.html) |

**[verified]** Elettra is a 2.0/2.4 GeV synchrotron in Trieste operating 28 beamlines, undergoing a 4th-generation "Elettra 2.0" upgrade (six-bend achromat, up to 32 beamlines) with first operation expected 2026. Its operator also runs the FERMI FEL on the same Tango control framework.

**Gaps:** Storage-ring circumference, exact emittance (current and Elettra 2.0 target), and bunch/fill parameters were **not** confirmed in a fetchable public source and should be pulled from the Elettra 2.0 design report or accelerator page before they appear on a deployment page. **[uncertain]**

---

## 2. Beamline catalog (imaging focus)

Elettra's "beamlines for imaging" page enumerates seven imaging-capable beamlines across six technique categories. SYRMEP (hard X-ray tomography, the 2-BM analog) and TwinMic (soft X-ray microscopy) are flagged as the most versatile. Energies/techniques are from each official beamline page. No beamlines invented; all trace to `elettra.eu`.

| Name | Technique | Energy | Notes | Source |
| --- | --- | --- | --- | --- |
| SYRMEP | Hard X-ray radiology / microtomography; absorption, propagation-based phase-contrast, diffraction-enhanced imaging | mono **10-40 keV** (see [§5](#5-data-management-processing) energy note); white/pink ~16-30 keV | Bending-magnet source; mono or white beam; clinical breast-CT program (SYRMA-3D) | [SYRMEP](https://www.elettra.eu/elettra-beamlines/syrmep.html) |
| TwinMic | Soft X-ray microscopy: integrated scanning (STXM) + full-field (TXM); LEXRF chemical mapping | 400-2200 eV (spans the water window) | 8 silicon drift detectors for LEXRF; Fresnel zone-plate focusing (50 nm outer zone) | [TwinMic](https://www.elettra.eu/elettra-beamlines/twinmic.html) |
| SISSI | IR microscopy: FTIR + nanoscale s-SNOM (SISSI-Nano) | mid-far IR | Two branches: SISSI-Bio, SISSI-Mat | [SISSI](https://www.elettra.eu/elettra-beamlines/sissi.html) |
| ESCA Microscopy | Scanning photoelectron microscope (SPEM) | 90-1200 eV | Spot to ~120 nm; energy resolution ~180 meV | [ESCA Microscopy](https://www.elettra.eu/elettra-beamlines/escamicroscopy.html) |
| Nanospectroscopy | SPELEEM (spectroscopic photoemission + LEEM) | 25-1000 eV | Lateral resolution near 10 nm | [Nanospectroscopy](https://www.elettra.eu/elettra-beamlines/nanospectroscopy.html) |
| NanoESCA | Energy-filtered PEEM | soft X-ray | ~50 nm imaging resolution; later spin-resolved upgrade | [NanoESCA](https://www.elettra.eu/elettra-beamlines/nanoesca.html) |
| Spectromicroscopy | Sub-um VUV ARPES via Schwarzschild optics | 27 / 74 eV | Energy/angular resolution to 14 meV / 0.150 deg | [Spectromicroscopy](https://www.elettra.eu/elettra-beamlines/spectromicroscopy.html) |

**[verified]** The seven-beamline imaging roster and the SYRMEP/TwinMic "most versatile" framing are stated on the official imaging page (the page that also carried an injected instruction block, ignored).

The X-ray Fluorescence (IAEA) beamline is **decommissioned** under Elettra 2.0; a successor (micrometric beam, in-vacuum undulator) is planned but its name/fate is unconfirmed. **[partly verified]** ([X-ray fluorescence page](https://www.elettra.eu/lightsources/elettra/elettra-beamlines/microfluorescence/x-ray-fluorescence.html))

### SYRMEP hardware detail (primary CORA target)

- **Source:** bending magnet (first BM of section 6); at 2.4 GeV critical energy 5.59 keV, field 1.45 T (the 1.45 T field independently corroborated). **[verified]** ([beamline-description](https://www.elettra.eu/lightsources/elettra/elettra-beamlines/syrmep/beamline-description.html), [PMC7941286](https://pmc.ncbi.nlm.nih.gov/articles/PMC7941286/))
- **Optics:** double-crystal Si(111) monochromator, fixed-exit Bragg geometry (20 mm vertical offset); monochromatic or white-beam mode. **[verified]**
- **Beam geometry:** laminar beam, ~120-160 x 4-5 mm² at ~20-23 m depending on page version / ring conditions; 7 mrad horizontal acceptance; sample ~23 m from source. **[partly verified]** (page-version variance noted, not resolved) ([specification](https://www.elettra.eu/lightsources/elettra/elettra-beamlines/syrmep/specification.html), [beamline-description](https://www.elettra.eu/lightsources/elettra/elettra-beamlines/syrmep/beamline-description.html))
- **Detectors:** official page lists a 12/16-bit CCD (4008x2672 px, 4.5 um pixel, PSF ~13 um) and a 16-bit sCMOS (2048x2048 px, effective pixel 0.9-5.7 um). Published configs also report Hamamatsu Orca Flash sCMOS on GGG:Eu scintillator and an XC Hydra (Direct Conversion AB) photon-counting detector for large-specimen CT. **[verified]** (the official CCD line re-fetched verbatim) ([beamline-description page 2](https://www.elettra.eu/lightsources/elettra/elettra-beamlines/syrmep/beamline-description/page-2.html), [PMC10161890](https://pmc.ncbi.nlm.nih.gov/articles/PMC10161890/))
- **Stages & scan modes:** five-axis sample stage; sample-to-detector sliding rail 3-160 cm; heavy-payload rotator up to 120 kg (1-20 deg/s, 0.02 deg precision). Modalities: step-and-shoot, continuous/fly, helical. **[verified]** ([beamline-description](https://www.elettra.eu/lightsources/elettra/elettra-beamlines/syrmep/beamline-description.html), [PMC10161890](https://pmc.ncbi.nlm.nih.gov/articles/PMC10161890/))

**Gaps (SYRMEP):** default routine-tomography camera + pixel size + field of view not pinned to a single authoritative source; SYRMA-3D clinical detector not separately sourced; standard (non-heavy) rotation-stage range. **[uncertain]**

---

## 3. Control-system stack, by layer

Elettra is **Tango-native** across both the synchrotron and the FERMI FEL. This is the floor/edge boundary a CORA deployment must model (analogous to the 2-BM EPICS-floor / TomoScan-orchestration seam, but here the floor is Tango and the orchestration is in-house). **No EPICS usage was found at the facility level.** **[verified]** ([control systems](https://www.elettra.eu/activities/control-systems/control-systems.html), [ICALEPCS 2023 TUPDP034](https://proceedings.jacow.org/icalepcs2023/papers/tupdp034.pdf), [ICALEPCS 2017 TUPHA208](https://proceedings.jacow.org/icalepcs2017/papers/tupha208.pdf))

> **Tango-membership nuance [verified]:** Elettra is an early adopter and current contract-signing Steering-Committee member of the Tango Controls collaboration, but Tango originated at ESRF (1998 proposal). The "first international presentation at ICALEPCS 1999 in Trieste" reflects the conference venue, not Elettra authorship. Do not describe Elettra as a Tango founder. ([tango-controls.org/about-us](https://www.tango-controls.org/about-us/))

### Device IO / interlock (the floor)

- **Tango** is the distributed device/control substrate; OS-independent, C++/Java/Python. **[verified]**
- **GeCo** (Gestione e Controllo) is the Elettra 2.0 beamline control rebuild, replacing ~30-year-old VME/LynxOS systems. Architecture: **Siemens S7-1500 PLCs** (CPU 1513-1PN) + ET200MP slaves over **PROFINET** for low-level/interlock control, with a Siemens CM 1543-1 exposing Modbus; a Python Tango device server reads a self-describing PLC Data Block and auto-creates one dynamic attribute per element. As of 2023, installed on two beamlines (two branch-lines each), controlling 56 and 111 elements with ~20 and ~40 interlock rules. **[verified]** ([ICALEPCS 2023 TUPDP034](https://proceedings.jacow.org/icalepcs2023/papers/tupdp034.pdf))
- **Motion / archiving:** standard Tango motion device servers (e.g. `pm600` for the McLennan PM600 stepper) and Tango historical archiving (HDB/HDB++, with `hdbextractor` and `cumbia-historicaldb`), plus an "Elettra Alarms" handler. **[verified]** ([ELETTRA-SincrotroneTrieste org](https://github.com/ELETTRA-SincrotroneTrieste))

### Orchestration + scan engine (the seam layer)

- **DonkiOrchestra** is Elettra's in-house, trigger-driven experiment-control/DAQ framework "for the Elettra and Fermi end-stations." An experiment is a sequence of phases, each started by a synchronization software trigger; a scheduler (**DonkiDirector**) drives parallel tasks (**DonkiPlayers**) in priority groups. DonkiDirector is in-house Python, uses **ZeroMQ** for the trigger train (each trigger carries a progressive index + priority tag), and stores data in **HDF5** archives. It was Tango-born but its Tango dependency "has been completely removed." **[verified]** ([ICALEPCS 2017 TUPHA208](https://proceedings.jacow.org/icalepcs2017/papers/tupha208.pdf))
- **Elettra 2.0 pipeline (current direction) [verified]:** ICALEPCS 2025 TUPD009 describes a five-layer facility-standard DAQ + processing pipeline, demonstrated at SYRMEP: (1) **GeCo** PLC interlock, (2) **Tango Controls** DAQ coordinated by an abstract **"Executer"** device server that runs the acquisition sequence and triggers post-acquisition processing, (3) **STP3 Web** reconstruction (a "transformative implementation" of the **MAPI** Modular Adaptive Processing Infrastructure; ASTRA + NiceGUI, Celery + MariaDB), (4) **VUO** portal mediating data/compute access and auth, (5) **Elettra Scientific Data Lake (EDL / "data@Elettra")**, a tiered lakehouse (NVMe->disk->tape) with FAIR metadata, DOIs, provenance. ([ICALEPCS 2025 TUPD009](https://proceedings.jacow.org/icalepcs2025/pdf/TUPD009.pdf)) **NB:** the working PDF path is `/pdf/TUPD009.pdf` (the `/papers/` path 404s); the DOI 10.18429/JACoW-ICALEPCS2025-TUPD009 is not yet Crossref-indexed.
- **Sardana is NOT used at Elettra** (it lists ALBA/DESY/MAX IV/Solaris/ESRF as supporters; Elettra is absent). **[verified]** ([sardana-controls.org](https://www.sardana-controls.org/))
- **Open seam question [uncertain]:** the relationship between DonkiOrchestra (2017-era scan engine) and the Elettra 2.0 "Executer" device server (2025) is not stated in sources; whether the Executer subsumes, wraps, or replaces DonkiOrchestra must be confirmed with staff.

### Web / GUI layer

- **DonkiWeb:** Python web server exposing a REST interface to Tango (read/write attributes, commands, websocket stream) + a JS library; auth via client IP or the Elettra **Virtual Unified Office (VUO)**. **[verified]** ([ICALEPCS 2023 TUPDP034](https://proceedings.jacow.org/icalepcs2023/papers/tupdp034.pdf))
- **cumbia / qtango:** Elettra's own C++/Qt control-system GUI frameworks with Tango + EPICS engine modules; cumbia v2.0 added Qt6 + CMake and HTTP/WebSocket transport switching. Newer end-station GUIs (e.g. TwinMic) also use the **Taurus** PyQt framework. **[verified]** ([cumbia-libs](https://github.com/ELETTRA-SincrotroneTrieste/cumbia-libs), [docs](https://elettra-sincrotronetrieste.github.io/cumbia-libs/))

### Legacy accelerator control

- The original Elettra accelerator control uses a three-layer architecture with a CERN-origin RPC middleware, "still used in its original form for controlling most of the power supplies of the Elettra storage ring." Newer work (booster, FERMI transfer lines) uses a Tango-based High Level Framework. **[verified]** ([IPAC2014 THPRO107](https://proceedings.jacow.org/IPAC2014/papers/thpro107.pdf)). Whether this legacy RPC layer is being retired under Elettra 2.0 is **not stated**. **[uncertain]**

---

## 4. Where the code lives

Public Elettra source is on **GitHub** (two orgs) and the public-readable self-hosted **`gitlab.elettra.eu`** (the primary live host). Repo facts from live GitHub/GitLab API (2026-06-28).

| Host / Org | Scale | Role |
| --- | --- | --- |
| [`ELETTRA-SincrotroneTrieste`](https://github.com/ELETTRA-SincrotroneTrieste) (GitHub) | ~53 repos | Control GUIs (cumbia/qtango), Tango device servers, HDB++ tooling, MXCuBE/ISPyB components |
| [`ElettraSciComp`](https://github.com/ElettraSciComp) (GitHub) | ~16 repos | Scientific Computing: tomography (STP), Pore3D, HDF5 tools |
| [`gitlab.elettra.eu`](https://gitlab.elettra.eu/explore/projects) (self-hosted GitLab CE) | ~1840 public projects | **Primary live code host**, committed daily; groups below |
| [`voltumna-linux`](https://github.com/voltumna-linux) (GitHub) | ~16 repos | Yocto/OpenEmbedded custom Linux distro "by and for Elettra" (incl. a Tango DCS/SCADA layer); active 2026 |

Notable `gitlab.elettra.eu` groups: `cs` (Control Systems: `cs/ds` Tango devices, `cs/gui`, `cs/lib` incl. cumbia, `cs/etc` incl. hdbpp/interlock/vacuum), `spe` (Software for experiments, per-beamline: `spe/gui` for xrf/xrd1/XPRESS/xafs), `syrmep_acquisition` (SYRMEP DAQ control + `tango_servers`), `FERMI-CR` (FERMI control room), `machine-learning`, `puma`. **[verified]** (open GitLab REST API)

Key repos for a CORA deployment:

| Repo | Host | What it is |
| --- | --- | --- |
| [cumbia-libs](https://github.com/ELETTRA-SincrotroneTrieste/cumbia-libs) | GitHub | C++/Qt control framework; Tango + EPICS engines; GPL-3.0 |
| [pm600](https://github.com/ELETTRA-SincrotroneTrieste/pm600) | GitHub | Tango device server for McLennan PM600 stepper |
| [hdbextractor](https://github.com/ELETTRA-SincrotroneTrieste/hdbextractor) | GitHub | C++ library to read Tango HDB/HDB++ archives |
| [STP-Core](https://github.com/ElettraSciComp/STP-Core) | GitHub | SYRMEP Tomo Project Python reconstruction engine; TDF/HDF5 I/O; GPL-3.0 |
| [STP-Gui](https://github.com/ElettraSciComp/STP-Gui) | GitHub | C#/.NET front end for STP-Core; GPL-3.0 |
| [Pore3D](https://github.com/ElettraSciComp/Pore3D) | GitHub | C/IDL toolbox for quantitative 3D micro-CT analysis; GPL-3.0 |
| [h5nuvola](https://github.com/ElettraSciComp/h5nuvola) | GitHub | Web HDF5 browser/visualizer with REST API (Flask+h5py+Bokeh) |
| [SciQC_HDF_filters](https://github.com/ElettraSciComp/SciQC_HDF_filters) | GitHub | Lossy HDF5 JPEG2000/JPEG-XR compression filters for micro-CT |
| [syrmep_acquisition](https://gitlab.elettra.eu/groups/syrmep_acquisition) | GitLab | SYRMEP DAQ control (acquisition counterpart to GitHub STP) |

**Excluded namesakes (NOT the synchrotron):** `ElettraRoboticsLab` (educational robotics), `Elettra-XRay-Laboratories`, `ElettraIT`. **DonkiOrchestra's** current public source location/license was **not** obviously in the public GitHub org; possibly behind `gitlab.elettra.eu` login. **[uncertain]**

**No public non-GitHub/GitLab VCS** (SourceForge/Bitbucket) confirmable for cumbia/qtango (WebSearch empty). **[uncertain]**

---

## 5. Data management + processing

- **Formats:** HDF5 is Elettra's standard scientific data/metadata container. For tomography, the in-house **TDF (Tomographic Data Format)** is an HDF5 working container; STP ships converters from native detector formats (ESRF EDF, Hamamatsu .his, PIXIRAD) into TDF and out to TIFF. TDF metadata follows the **DataExchange** model (`implements='exchange:measurement:provenance'`), **not** strict NeXus. **[verified]** ([STP-Core](https://github.com/ElettraSciComp/STP-Core), [tdf.py](https://raw.githubusercontent.com/ElettraSciComp/STP-Core/master/STP-Core/stpio/tdf.py))
- **Catalog / system of record [verified]:** Elettra runs a **custom in-house catalog**, **NOT SciCat / ICAT / Invenio** (none found in either GitHub org or `gitlab.elettra.eu`). The Open Access Data Portal is a bespoke module of the **VUO** running on **Oracle PL/SQL Web Toolkit (mod_plsql)**; DOIs resolve to `vuo.elettra.eu/pls/vuo/open_access_data_portal...`. ([VUO portal sample](https://vuo.elettra.eu/pls/vuo/open_access_data_portal.show_view_investigation?FRM_ID=61089))
- **DOI practice [verified]:** per-dataset DataCite minting, two clients (both created 2020-03-31): `eta.elettra` (prefix **10.34965**, ~1,506 dataset DOIs) and `eta.ceric` (prefix **10.34967**, 7 DOIs). ([api.datacite.org/clients/eta.elettra](https://api.datacite.org/clients/eta.elettra), [eta.ceric](https://api.datacite.org/clients/eta.ceric))
- **Elettra Scientific Data Lake (EDL):** the Elettra 2.0 tiered storage tier (NVMe->disk->tape), with HDF5 as the target facility-wide format. Performance/scale figures (3 TB/day, 14 PB tape, 10-20 GB/s SYRMEP-LS) trace to **unpublished/submitted refs** and are explicit **projections / goals**, not current state. **[partly verified]** ([ICALEPCS 2025 TUPD009](https://proceedings.jacow.org/icalepcs2025/pdf/TUPD009.pdf))
- **MX path is separate:** the XRD2/MX beamline uses **ISPyB + MXCuBE** (MariaDB, Diamond lineage) as a domain catalog, distinct from the facility VUO/EDL record. **[partly verified]** ([ispyb-api](https://github.com/ELETTRA-SincrotroneTrieste/ispyb-api))

### Reconstruction / analysis toolchain

- **SYRMEP Tomo Project (STP):** reconstruction for parallel-beam propagation-based phase-contrast CT; split into **STP-Core** (Python engine) + **STP-Gui** (C#/.NET front end), GPL-3.0, developed with Univ. Trieste + CNR Nanotec. Integrates the **ASTRA Toolbox** and **TomoPy** with optional CUDA. Algorithms verified live in `reconstruct/` (gridrec, astra, fista_tv, mr_fbp, sirt_fbp); phase retrieval (TIE-HOM/Paganin, GDEI); six ring-removal methods. **[verified]** ([STP-Gui](https://github.com/ElettraSciComp/STP-Gui), [STP-Core](https://github.com/ElettraSciComp/STP-Core))
- **STP3 Web (Elettra 2.0):** the MAPI-based successor (ASTRA + NiceGUI, Celery + MariaDB) named in the 2025 pipeline paper. **[verified]**
- **Pore3D:** C toolbox for quantitative 3D micro-CT analysis (filtering, segmentation, skeletonization, morphometry), exposed via **IDL** (requires proprietary IDL runtime; no Python successor confirmed). **[verified]** ([Pore3D](https://github.com/ElettraSciComp/Pore3D))
- **SciQC HDF filters:** lossy JPEG2000/JPEG-XR HDF5 plugins for micro-CT (corroborated by Meas. Sci. Technol. 2018). **[verified]**

**Gaps (data):** no fetchable formal **data-management policy** (retention/embargo/ownership), candidate URLs 404'd; sampled DataCite records had empty rightsList/dates. Whether current SYRMEP acquisition writes NeXus/NXtomo vs DataExchange-style TDF is unconfirmed (STP-Core last pushed 2021). **[uncertain]**

---

## 6. The CORA seam (initial read)

This is a first pass, not a committed seam. It applies the same 2-BM/FXI lens: Tango and device IO are the floor CORA never replaces; the higher scan/orchestration layer is where CORA replaces or drives through.

**Where Tango stays the floor.** Elettra's device/interlock layer is Tango + GeCo PLCs (Siemens S7-1500/PROFINET) + Tango motion/detector servers + HDB++ archiving. CORA's ControlPort would actuate **through** this Tango floor exactly as it does over EPICS at 2-BM/FXI; CORA never owns Tango device servers, PLC interlock logic, or the device layer. GeCo safety/interlock and the legacy RPC ring-control layer are out of scope.

**What CORA would replace or drive through.** The orchestration layer is **DonkiOrchestra/DonkiDirector** (trigger-priority scan engine over Tango), with the Elettra 2.0 **"Executer"** device server as its emerging successor. This is the layer the 2-BM seam designates as CORA's: CORA's EdgeConductor would replace the scan/alignment orchestration that DonkiDirector/Executer performs today, conducting over the Tango floor. DonkiDirector's experiment-as-sequence-of-phases maps onto CORA's run/acquisition modeling, and its ZeroMQ trigger train + HDF5 collection is functionally the orchestration + capture legs.

**System of record.** Elettra's record surface is the **VUO + Open Access Data Portal (custom Oracle/mod_plsql) + EDL data lake**, with per-dataset DataCite DOIs. There is **no SciCat/ICAT-style experiment catalog**; the catalog role is split across VUO and EDL. This split is exactly where CORA's event-sourced system-of-record for the experiment would sit, owning proposal->sample->run->acquisition->result provenance, treating the Open Access Data Portal as a downstream publication target (consistent with "we do our own data of record").

**Reconstruction/analysis stays floor tooling.** STP/STP3, Pore3D, ASTRA/TomoPy, SciQC filters are post-acquisition tools CORA would **record as Method/Compute provenance** (compute-as-adapter-axis), not reimplement.

**Open design questions.**
- DonkiOrchestra vs Elettra 2.0 "Executer": which is the actual orchestration boundary CORA targets, and is the choice facility-wide or per-beamline?
- Replace vs drive-through at that boundary (the 2-BM "edge promoted to intended" vs lighter drive-through posture).
- Does CORA subsume the DataExchange/TDF (or future NeXus) metadata layer, or write alongside during transition?
- How CORA's Trust/governance maps to the VUO user-office and Elettra's role/auth model.

---

## 7. Confidence + gaps

**Well-corroborated (multiple primary sources or verified):**
- Facility identity: 2.0/2.4 GeV, 28 beamlines, Elettra 2.0 six-bend upgrade, 2026 first operation. **[verified]**
- Tango as the device-control floor across synchrotron + FERMI; no EPICS. **[verified]**
- DonkiOrchestra/DonkiDirector as the in-house scan engine; Sardana NOT used. **[verified]**
- Elettra 2.0 five-layer pipeline (GeCo -> Tango/Executer -> STP3/MAPI -> VUO -> EDL). **[verified]**
- SYRMEP source/optics/detectors/stages/scan modes. **[verified]**
- Catalog = custom Oracle/mod_plsql VUO module (not SciCat/ICAT); per-dataset DataCite DOIs (prefixes 10.34965 / 10.34967). **[verified]**
- STP/Pore3D reconstruction toolchain + repo locations. **[verified]**

**Uncertain or single-source:**
- Ring circumference, emittance, fill parameters: **not confirmed**; pull from Elettra 2.0 design report. **[uncertain]**
- SYRMEP white/pink-beam 16-30 keV average: paywall-only, not independently re-verified (mono 10-40 keV is solid). **[partly verified]**
- DonkiOrchestra vs "Executer" relationship; DonkiOrchestra public source location. **[uncertain]**
- Legacy RPC ring-control retirement under Elettra 2.0. **[uncertain]**
- EDL scale/throughput figures (projections, unpublished refs). **[partly verified]**
- Formal data policy (embargo/retention), no fetchable document. **[uncertain]**
- Whether MXCuBE/ISPyB are deployed on a live MX beamline vs mirrored for contribution. **[partly verified]**

**What to ask facility staff:**
1. Storage-ring circumference, emittance (current + Elettra 2.0 target), bunch/fill parameters.
2. Authoritative SYRMEP energy bounds per mode (mono vs white/pink), default routine-tomography detector + pixel size + FOV.
3. The orchestration boundary: is DonkiOrchestra still the scan engine, or has the Elettra 2.0 "Executer" device server replaced it, and is it facility-wide?
4. Per-beamline device inventory (Tango device namespaces, PLC/controller boxes, motion axes, detectors) on `gitlab.elettra.eu` private groups.
5. Data of record: VUO/EDL persistence model, current acquisition metadata format (DataExchange TDF vs NeXus/NXtomo), where raw data lands.
6. Data-management policy: retention, embargo, ownership, DOI minting triggers.
7. Proposal/user-office system behind VUO, role/permission model, for the governance seam.

---

## 8. Key papers and proceedings

| Paper | Venue | Why it matters | DOI / URL |
| --- | --- | --- | --- |
| Integrated Data Acquisition and Processing Pipelines for Users at Elettra 2.0 | ICALEPCS 2025 | The authoritative five-layer Elettra 2.0 DAQ + processing pipeline (GeCo/Tango-Executer/STP3-MAPI/VUO/EDL) | [TUPD009 PDF](https://proceedings.jacow.org/icalepcs2025/pdf/TUPD009.pdf) (DOI 10.18429/JACoW-ICALEPCS2025-TUPD009, not yet Crossref-indexed) |
| GeCo: a new beamline control system for Elettra 2.0 | ICALEPCS 2023 | PLC-based interlock + Tango beamline control; DonkiWeb REST layer | [TUPDP034](https://proceedings.jacow.org/icalepcs2023/papers/tupdp034.pdf) |
| DonkiOrchestra: a trigger-based data acquisition framework | ICALEPCS 2017 | The in-house scan/sequencing engine (DonkiDirector/DonkiPlayer, ZeroMQ triggers, HDF5) | [TUPHA208](https://proceedings.jacow.org/icalepcs2017/papers/tupha208.pdf) |
| SYRMEP beamline: state of the art, upgrades and future prospects | Eur. Phys. J. Plus 139:880 (2024) | Authoritative SYRMEP review; mono 10-40 keV; SYRMEP-2 prospects | [10.1140/epjp/s13360-024-05489-1](https://doi.org/10.1140/epjp/s13360-024-05489-1) |
| A large-field-of-view setup for SYRMEP photon-counting micro-CT | J. Synchrotron Rad. (2023) | XC Hydra photon-counting detector, helical CT, large-specimen modes | [10.1107/S1600577523001649](https://doi.org/10.1107/S1600577523001649) |
| SYRMEP Tomo Project: a GUI for customizing CT reconstruction workflows | Adv. Struct. Chem. Imaging (2017) | The STP reconstruction GUI canonical citation | [10.1186/s40679-016-0036-8](https://doi.org/10.1186/s40679-016-0036-8) |
| Pore3D: a software library for quantitative analysis of porous media | Nucl. Instrum. Methods A 615 (2010) | The Pore3D analysis toolbox canonical citation | [10.1016/j.nima.2010.02.063](https://doi.org/10.1016/j.nima.2010.02.063) |
| Original Elettra accelerator control system (legacy RPC) | IPAC 2014 | Documents the CERN-origin RPC ring-control layer still in use | [THPRO107](https://proceedings.jacow.org/IPAC2014/papers/thpro107.pdf) |

**Coverage gaps in the literature search:** WebSearch returned empty all session; several primary papers (IUCr, Springer, ResearchGate) were paywalled or blocked WebFetch (403); the EPJ Plus 2024 review body and the SYRMEP white/pink-beam figure were not read directly (Crossref abstract corroborates the 10-40 keV mono headline). The Elettra 2.0 EDL/MAPI/Executer detail traces to unpublished refs cited within TUPD009.

---

## 9. Source list

**Facility (hardware facts):**
- Elettra: https://www.elettra.eu/lightsources/elettra.html
- Beamlines roster: https://www.elettra.eu/lightsources/elettra/beamlines.html
- Beamlines for imaging: https://www.elettra.eu/lightsources/elettra/elettra-beamlines/beamlines-for-imaging-at-elettra.html
- Beamline pages: [SYRMEP](https://www.elettra.eu/elettra-beamlines/syrmep.html), [TwinMic](https://www.elettra.eu/elettra-beamlines/twinmic.html), [SISSI](https://www.elettra.eu/elettra-beamlines/sissi.html), [ESCA Microscopy](https://www.elettra.eu/elettra-beamlines/escamicroscopy.html), [Nanospectroscopy](https://www.elettra.eu/elettra-beamlines/nanospectroscopy.html), [NanoESCA](https://www.elettra.eu/elettra-beamlines/nanoesca.html), [Spectromicroscopy](https://www.elettra.eu/elettra-beamlines/spectromicroscopy.html)
- SYRMEP specification: https://www.elettra.eu/lightsources/elettra/elettra-beamlines/syrmep/specification.html
- SYRMEP beamline-description: https://www.elettra.eu/lightsources/elettra/elettra-beamlines/syrmep/beamline-description.html (+ [page 2](https://www.elettra.eu/lightsources/elettra/elettra-beamlines/syrmep/beamline-description/page-2.html))

**Control software (orgs / hosts):**
- ELETTRA-SincrotroneTrieste (GitHub): https://github.com/ELETTRA-SincrotroneTrieste
- ElettraSciComp (GitHub): https://github.com/ElettraSciComp
- gitlab.elettra.eu (self-hosted GitLab): https://gitlab.elettra.eu/explore/projects
- voltumna-linux (GitHub): https://github.com/voltumna-linux

**Control software (repos):**
- cumbia-libs: https://github.com/ELETTRA-SincrotroneTrieste/cumbia-libs (docs https://elettra-sincrotronetrieste.github.io/cumbia-libs/)
- pm600: https://github.com/ELETTRA-SincrotroneTrieste/pm600
- hdbextractor: https://github.com/ELETTRA-SincrotroneTrieste/hdbextractor
- STP-Core: https://github.com/ElettraSciComp/STP-Core
- STP-Gui: https://github.com/ElettraSciComp/STP-Gui
- Pore3D: https://github.com/ElettraSciComp/Pore3D
- h5nuvola: https://github.com/ElettraSciComp/h5nuvola
- SciQC_HDF_filters: https://github.com/ElettraSciComp/SciQC_HDF_filters
- syrmep_acquisition (GitLab): https://gitlab.elettra.eu/groups/syrmep_acquisition

**Data + catalog:**
- VUO Open Access Data Portal (sample record): https://vuo.elettra.eu/pls/vuo/open_access_data_portal.show_view_investigation?FRM_ID=61089
- DataCite client eta.elettra: https://api.datacite.org/clients/eta.elettra
- DataCite client eta.ceric: https://api.datacite.org/clients/eta.ceric
- TDF format source: https://raw.githubusercontent.com/ElettraSciComp/STP-Core/master/STP-Core/stpio/tdf.py

**Papers / proceedings:**
- ICALEPCS 2025 TUPD009 (Elettra 2.0 pipeline): https://proceedings.jacow.org/icalepcs2025/pdf/TUPD009.pdf
- ICALEPCS 2023 TUPDP034 (GeCo): https://proceedings.jacow.org/icalepcs2023/papers/tupdp034.pdf
- ICALEPCS 2017 TUPHA208 (DonkiOrchestra): https://proceedings.jacow.org/icalepcs2017/papers/tupha208.pdf
- EPJ Plus 2024 (SYRMEP review): https://doi.org/10.1140/epjp/s13360-024-05489-1
- J. Synchrotron Rad. 2023 (SYRMEP large-FOV): https://doi.org/10.1107/S1600577523001649
- Adv. Struct. Chem. Imaging 2017 (STP GUI): https://doi.org/10.1186/s40679-016-0036-8
- Nucl. Instrum. Methods A 2010 (Pore3D): https://doi.org/10.1016/j.nima.2010.02.063
- IPAC 2014 THPRO107 (legacy accelerator control): https://proceedings.jacow.org/IPAC2014/papers/thpro107.pdf
- Tango Controls about: https://www.tango-controls.org/about-us/
- Sardana (NOT used at Elettra, comparison only): https://www.sardana-controls.org/

**Internal-login (named, not linked as reachable):** VUO authenticated portal, private `gitlab.elettra.eu` groups, DonkiOrchestra source (location unconfirmed).
