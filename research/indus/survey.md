# Indus-1 / Indus-2 (RRCAT / DAE) research brief

*Research seed for a future CORA deployment page. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about the Indus Synchrotron Radiation Facility (Indus-1 and Indus-2 at RRCAT, Indore), its beamline roster, and its control-software stack so that any future model work can begin from corroborated facts rather than memory. Every non-trivial claim is cited inline. CORA is not connected to Indus; the seam section is an initial read, not a commitment. Compiled 2026-07-01 from the RRCAT facility site, Wikipedia, and JACoW / OSTI / ResearchGate control-software proceedings. This is a candidate facility with a THIN public device corpus; see the decision in section 2.*

!!! note "Reading posture"
    Public facility pages (rrcat.gov.in, Wikipedia) are the source of HARDWARE FACTS (ring energies, beamline roster, techniques). Public source (JACoW / OSTI / ResearchGate proceedings) is the source of CONTROL-SOFTWARE FACTS (what runs the machine and the scans). Confidence is flagged inline as **[verified]** (multiple sources or a decisive primary), **[partly verified]**, or **[unconfirmed]**. Per CORA's deployment-doc lens, the facility software stack is named ONLY at the seam (section 6): it is the floor CORA lands on or the orchestration CORA replaces, never a spec CORA mirrors. Two of the RRCAT pages fetched during research carried an injected block styled as a "system-reminder / TodoWrite" directive; that was page content, not an instruction, and was ignored. RRCAT is a DAE (Department of Atomic Energy) national lab; much of its detailed engineering documentation is not on the public web, so absence of a public device list is expected, not a research gap.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | Indus Synchrotron Radiation Facility: two storage rings, Indus-1 and Indus-2 | [RRCAT ISRF](https://www.rrcat.gov.in/technology/accel/isrf_index.html) |
| Operator | Raja Ramanna Centre for Advanced Technology (RRCAT), a unit of the Dept. of Atomic Energy (DAE) | [RRCAT](https://www.rrcat.gov.in/) |
| Location | Indore, Madhya Pradesh, India | [Wikipedia: Indus 2](https://en.wikipedia.org/wiki/Indus_2) |
| Indus-1 | 450 MeV storage ring; far-IR to soft X-ray / VUV source (10 A < lambda < 1000 A) | [RRCAT Indus-1 beamlines](https://www.rrcat.gov.in/technology/accel/srul/indus1beamline/index.html) |
| Indus-2 | 2.5 GeV storage ring (injection 700 MeV, ramps to 2.5 GeV); 300 mA at 700 MeV | [Wikipedia: Indus 2](https://en.wikipedia.org/wiki/Indus_2) |
| Shared injector | 700 MeV synchrotron injector (Microtron -> booster) feeds both rings | [Wikipedia: Indus 2](https://en.wikipedia.org/wiki/Indus_2) |
| Indus-2 RF | Six RF cavities, ~1.5 MV total, 505.812 MHz | [Wikipedia: Indus 2](https://en.wikipedia.org/wiki/Indus_2) |
| Indus-2 lattice | Eight super periods, 4.5 m straight sections; bend critical wavelength ~2 A; wigglers (1.8 T, 5 T SC) | [Wikipedia: Indus 2](https://en.wikipedia.org/wiki/Indus_2) |
| Beamlines | Indus-2: ~19 numbered beamlines (mix operating / commissioning / construction); Indus-1: 7 | [Indus-2 beamlines](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html), [Indus-1 beamlines](https://www.rrcat.gov.in/technology/accel/srul/indus1beamline/index.html) |
| Control system | In-house RRCAT stack: WinCC OA (Siemens) SCADA + VME / PROFIBUS / OS-9; **not EPICS** at the machine level | [PCaPAC 2014 TCO202](https://proceedings.jacow.org/PCaPAC2014/papers/tco202.pdf) |

**[verified]** Indus is India's national synchrotron facility: two storage rings (Indus-1 at 450 MeV, a far-IR-to-VUV/soft-X-ray source; Indus-2 at 2.5 GeV, a hard-X-ray source with bend critical wavelength ~2 A and 1.8 T / 5 T superconducting wigglers) sharing a 700 MeV injector, operated by RRCAT / DAE at Indore. Indus-2 runs round-the-clock for users ([PCaPAC 2014 TCO202](https://proceedings.jacow.org/PCaPAC2014/papers/tco202.pdf)). The most citable CORA hook is negative but real: the control and data-of-record stack is a fully in-house SCADA + VME system with MS-SQL logging and home-grown web tools (Indus Online, Flogbook, Eplanner), so there is no external event-sourced governance/provenance spine of the kind CORA provides. That absence is exactly the gap the CORA spine addresses, but it also means nothing here is buildable from public device source.

**Circumference / emittance gap:** Indus-2 circumference (~172 m is a commonly-cited figure) and lattice emittance were **not** confirmed in a fetchable public source during this pass; the Wikipedia article omits circumference and the RRCAT machine page was not read in detail. Pull from the Indus-2 design report or an RRCAT accelerator page before any deployment page quotes a number. **[unconfirmed]**

---

## 2. Candidate beamlines

**Source-of-record posture (the decision-driving fact).** RRCAT does **not** publish per-beamline device configuration with real control handles. There is no public `dodal`/Beacon/`*-bits`-equivalent, no public GitHub/GitLab org for Indus beamline device support, and no per-beamline PV or device inventory on the web. The public beamline pages are prose descriptions with technique names only; the control-software proceedings describe architecture, not device lists. **A Tier-2 device pass is therefore NOT buildable from public source for any Indus beamline.** Device topology (PV/handle inventory, controller boxes, motion axes, detectors) is entirely a staff question (section 7). Inferring it from the shared VME/SCADA architecture is not source. **[verified]** (verified as an absence: no public device source found across RRCAT site, GitHub, OSTI, ResearchGate).

Given that, the table below is a technique-level roster (hardware facts from RRCAT pages), NOT a modellable device map. The "control source" column is uniform: firewalled / not public.

**Indus-2 (2.5 GeV, hard X-ray):**

| Beamline | ID | Technique | Control source | Source |
| --- | --- | --- | --- | --- |
| SXAS | BL-01 | Soft X-ray absorption spectroscopy | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| Engineering Applications | BL-02 | engineering / materials | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| Soft X-ray reflectivity | BL-03 | reflectometry | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| Imaging | BL-04 | X-ray imaging / radiography (imaging-line, CORA-relevant) | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| AMOS | BL-05 | atomic/molecular/optical science | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| X-ray Lithography | BL-07 | LIGA / lithography | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| EXAFS | BL-08 | dispersive/absorption EXAFS | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| EXAFS Scanning | BL-09 | scanning-DCM EXAFS / XANES | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| ARPES | BL-10 | angle-resolved photoemission | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| Extreme conditions AD/ED-XRD | BL-11 | high-pressure angle-/energy-dispersive XRD | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| ADXRD | BL-12 | angle-dispersive X-ray diffraction | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| GIXS | BL-13 | grazing-incidence X-ray scattering | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| XPES | BL-14 | X-ray photoelectron spectroscopy | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| XRF-microprobe | BL-16 | X-ray fluorescence microprobe | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| SWAXS | BL-18 | small/wide-angle X-ray scattering | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| XMCD | BL-20 | X-ray magnetic circular dichroism | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| Protein Crystallography | BL-21 | MX | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| ARPES/PEEM | BL-22 | photoemission microscopy (design & construction) | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |
| Visible / X-ray beam diagnostics | BL-23 / BL-24 | machine diagnostics (not user science) | not public | [roster](https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html) |

**Indus-1 (450 MeV, VUV / soft X-ray):** Reflectivity; AIPES (angle-integrated photoemission); ARPES; Photo Physics; High-Resolution VUV; Infrared; PASS. **[verified]** ([Indus-1 beamlines](https://www.rrcat.gov.in/technology/accel/srul/indus1beamline/index.html)). These are VUV/soft-X-ray and spectroscopy lines, further from CORA's imaging/tomography pilot ladder than the Indus-2 hard-X-ray lines.

**Energy ranges, detectors, and source-type per beamline are NOT catalogued here** because the individual RRCAT beamline pages were not each fetched and the roster index carries only technique names; inventing ranges/detectors would be fabrication. They are staff questions.

**Modellable decision.** Nothing at Indus is Tier-2 modellable from public source today. The strongest *conceptual* pick for CORA's imaging/tomography-leaning ladder is **BL-04 (Imaging)** on Indus-2, with the two EXAFS scanning lines (BL-08/BL-09) as secondary interest because a scanning DCM is the kind of routine CORA's energy-scan Capability wants, and one EXAFS DAQ paper exists to seed a Tier-2 ask ([ResearchGate 265695020](https://www.researchgate.net/publication/265695020)). But all three would require staff-provided device inventories before any facts pass. **Recommendation: keep Indus as a candidate stub, roster-only, and revisit only if a deployment is actually proposed and RRCAT staff can share a device list.** It is worth a Tier-1 home like ALS / PETRA III, not more.

**Identifier-scheme note:** Indus-2 names beamlines `BL-NN` (a flat two-digit port index, e.g. `BL-04`, `BL-21`); Indus-1 uses technique-named lines with no number scheme. Neither matches the APS `sector.station` scheme the pilot assumes, and the two rings do not share a numbering namespace. This is a descriptor / identifier-scheme difference to model (a facility with two rings under one operator, each with its own beamline naming), not a hardware difference. **[verified]**

---

## 3. Control-system stack, by layer

The Indus machine control system is **in-house, designed and maintained by RRCAT's Accelerator Control Section**, and is explicitly NOT an EPICS facility at the accelerator level. It predates and sits outside the EPICS / Tango / BLISS mainstream; it is a WinCC OA SCADA front end over a home-grown VME / PROFIBUS / OS-9 field layer. **[verified]** ([PCaPAC 2014 TCO202](https://proceedings.jacow.org/PCaPAC2014/papers/tco202.pdf), [RRCAT i2ControlSystems](https://www.rrcat.gov.in/technology/accel/indus/acs/i2ControlSystems.html)).

### Device IO (the floor)

A three-layer distributed architecture, all home-grown around the VME bus. The three-tier framing is on the [RRCAT i2ControlSystems](https://www.rrcat.gov.in/technology/accel/indus/acs/i2ControlSystems.html) overview; the specific figures below (PROFIBUS 750 kbaud, MSIS ~400 signals, the L2/L3 CPU and bus details) are from [PCaPAC 2014 TCO202](https://proceedings.jacow.org/PCaPAC2014/papers/tco202.pdf), which is the decisive primary. **[verified]**:
- **Layer 3 (Equipment Control):** ~150 Equipment Control Stations (ECs), each a Motorola 680x0 (MC68000) CPU on VME with a PROFIBUS controller plus ADC / DAC / DIO / relay / ramp / timing boards. Real-time OS-9. This is the floor that surfaces hardware.
- **Layer 2 (Supervisory Control):** VME supervisory controllers (MC68040, on-board Ethernet), OS-9, C code cross-developed from UNIX/Windows NT. Talks PROFIBUS (RS-485, ~750 kbaud) down to L3, Ethernet (100 Mbps) up to L1.
- The **Machine Safety Interlock System (MSIS)** is a separate home-grown VME distributed system (~400 critical signals) on a custom RS-485 link, deliberately NOT on PROFIBUS, for fail-safe reliability; it also ingests beamline front-end signals. **[verified]**

There is no published PV/handle namespace; addressing is internal to the ECs and their API managers. This floor has no public analogue to an EPICS IOC list.

### Scan orchestration (the seam layer)

At the **machine** level, the supervisory/UI layer is **WinCC OA** (Siemens SCADA, formerly PVSS II / ETM), running on Windows client/server machines, integrating custom **API managers** (C++ over the PVSS API) that bridge SCADA to the L2 VME layer, plus **LabVIEW and Matlab** modules (e.g. global slow-orbit feedback in Matlab+PVSS; LCW plant in LabVIEW). "About 10,000 I/Os in all" monitored at 1 Hz. **[verified]** ([PCaPAC 2014 TCO202](https://proceedings.jacow.org/PCaPAC2014/papers/tco202.pdf), [RRCAT pvss](https://www.rrcat.gov.in/technology/accel/indus/acs/pvss.html)).

At the **beamline** level there is no single unified scan engine in public source. Per-beamline experiment control and DAQ appear heterogeneous and mostly **LabVIEW-based GUIs**, with EPICS used selectively at specific beamlines (the scanning-EXAFS DCM is driven via "EPICS through LabVIEW", reusing open BESSY code; the XRD line drives a six-circle diffractometer over EIA-232/Ethernet; a diagnostic-beamline DAQ is LabVIEW). **[partly verified]** ([EXAFS DAQ, ResearchGate 265695020](https://www.researchgate.net/publication/265695020); [XRD DAQ, OSTI 21410315](https://www.osti.gov/biblio/21410315); [diagnostic DAQ, OSTI 22265584](https://www.osti.gov/etdeweb/biblio/22265584)). So EPICS *does* appear at the beamline edge in at least one case, even though it is absent from the machine core; the ACS division's own skills list names "EPICS" alongside "WinCCOA, Labview, Java, Visual C++" ([RRCAT ACS](https://www.rrcat.gov.in/technology/accel/indus/acs/index.html)). The true per-beamline breakdown of LabVIEW vs EPICS vs bespoke is a staff question.

### Fast paths and exceptions

- **Timing system:** custom VME timing with a coincidence-generator board (booster 31.613 MHz vs Indus-2 505.6 MHz, the same RF frequency Wikipedia gives more precisely as 505.812 MHz, see section 1), sub-ns delay resolution, optical-fiber analog reference distribution. **[verified]**
- **Orbit feedback:** global SOFB (Matlab+PVSS, ~30 um) and a phased global FOFB (FPGA + fast correctors/BPIs, ~3 um at 50 Hz vertical), bunch-by-bunch feedback integrated with the control system. **[verified]** These are machine-side, below any CORA seam.

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| RRCAT Accelerator Control Section (internal) | machine control system: WinCC OA + VME/OS-9 API managers, MSIS, timing, feedback | [PCaPAC 2014 TCO202](https://proceedings.jacow.org/PCaPAC2014/papers/tco202.pdf) |
| Per-beamline groups (internal) | beamline experiment control / DAQ (LabVIEW; EPICS-via-LabVIEW at EXAFS) | [ResearchGate 265695020](https://www.researchgate.net/publication/265695020), [OSTI 21410315](https://www.osti.gov/biblio/21410315) |
| `info.rrcat.gov.in/beamline/` | user beamline online-booking / registration portal | [Indus beamline booking](https://info.rrcat.gov.in/beamline/) |

**Why a full device model is NOT integrity-buildable from public source.** The per-beamline device list with real handles is not public: no controls repo, no device-config file, no PV namespace, no GitHub/GitLab org for Indus was found (GitHub repository search for "RRCAT Indus beamline" returned zero results). RRCAT is a DAE national lab and its engineering source is internal. The control-software knowledge that *is* public lives in JACoW / OSTI / ResearchGate proceedings, which describe architecture, not device inventories. Therefore all device topology routes to the staff questions (section 7); it must not be inferred from the shared VME/SCADA architecture, which tells you the substrate but not the per-beamline Assets. **[verified]** as an absence.

---

## 5. Data management

The machine data-of-record is a **central MS-SQL database**: ~10,000 machine parameters logged at 1 Hz (upgraded from a direct-SCADA-write scheme to a Java bulk-insert pipeline with per-data-type tables and sliding-window partitioning), plus logging of all operator interactions and system events. On top of it sit home-grown **web tools**: Indus Online (live/historical/statistical data), Fault Information System, Machine Status Information System, **Flogbook / Elogbook** (electronic shift logs and fault tracking), and **Eplanner** (machine-activity management). **[verified]** ([PCaPAC 2014 TCO202](https://proceedings.jacow.org/PCaPAC2014/papers/tco202.pdf)).

No public facility-wide *experiment* data catalog (SciCat / ICAT-equivalent), no stated NeXus/HDF5 standardization layer, and no ELN for user experiment data were found in public source; per-beamline DAQ appears to write local formats. The user-facing surface is the **beamline online-booking / registration portal** ([info.rrcat.gov.in/beamline](https://info.rrcat.gov.in/beamline/)), which handles proposal/user registration but whose scheduling and data-catalog scope could not be settled publicly. **[partly verified]** The data-of-record picture is machine-centric (SQL time-series + logbooks); the experiment-data catalog is an open question. This matters for the seam: there is little existing experiment-catalog to contest, which strengthens CORA's system-of-record position but also means the ingestion/provenance chain would be largely greenfield.

---

## 6. The CORA seam (initial read)

First pass, not a committed seam. Applies the 2-BM / FXI lens, but with the strong caveat that this is a candidate stub: no device source is public, so any seam read is architectural, not device-grounded.

**Where the floor stays the floor (drive through, never CORA).** The device IO floor at Indus is the home-grown VME / OS-9 / PROFIBUS EC layer, not EPICS. This is the single biggest departure from the APS pilot: the APS ControlPort model assumes an EPICS Channel Access floor, and that assumption **does not carry over** at the machine level here. CORA would need a control substrate that talks either to the WinCC OA supervisory layer (via the PVSS API / OPC-UA that WinCC OA exposes) or to per-beamline LabVIEW/EPICS edges, and the shape differs per beamline. Where a beamline already runs EPICS-via-LabVIEW (EXAFS DCM), the ControlPort model partially carries over; elsewhere it is a new adapter. This widens the ControlPort surface and is the central unknown.

**What CORA replaces (edge orchestration).** There is no single facility-wide beamline scan engine to replace; beamline orchestration is per-beamline LabVIEW/bespoke. CORA's EdgeConductor would conduct scan/alignment routines that today are LabVIEW GUIs, incrementally and per-beamline. Because these are bespoke rather than a solid shared framework (unlike bluesky at Sirius/NSLS-II or BLISS at ESRF), the "treat it as data to learn from" posture applies weakly: there is little uniform prior art to mine. The machine-side WinCC OA + API-manager orchestration is out of scope (accelerator operations, below the experiment seam); CORA never touches ring control.

**Source-of-truth contest (data).** Weak contest on the experiment side: no public experiment-data catalog to invert or project into. The machine-side MS-SQL logging + Flogbook/Elogbook is accelerator-operations data, not experiment data of record, so it is not a direct competitor for CORA's "system of record for the experiment" claim. CORA would bring its own event-sourced spine into largely open territory. The user-booking portal is a scheduling/identity source to read, not replace.

**Coexist.** The beamline booking/registration portal (read for proposal/user identity), any HPC/reconstruction the imaging line uses (a port roundtrip, unknown publicly), the machine logbooks (subsumed only at the experiment-debrief layer, not the accelerator-ops layer). Defer all of these until a real deployment is in scope.

---

## 7. Open questions (for facility staff)

These could not be settled from public sources and need RRCAT confirmation before any seam lock. Ask the **Accelerator Control Section, RRCAT** (the PCaPAC control-system authors) and the relevant beamline groups.

1. **Per-beamline device inventory** for the CORA-relevant lines (BL-04 Imaging first; BL-08/BL-09 EXAFS; BL-11/BL-12 XRD): what are the motion axes, controller boxes, detectors, and their control handles? Nothing of this is public and it is the gate for any Tier-2 pass.
2. **Beamline control substrate per line:** which beamlines run LabVIEW GUIs, which run EPICS (as the EXAFS DCM does via EPICS-through-LabVIEW), and which are bespoke? Is there any move toward a unified beamline scan engine?
3. **The ControlPort boundary:** does CORA drive through WinCC OA's supervisory API (PVSS API / OPC-UA) at the beamline front-end, or directly against per-beamline LabVIEW/EPICS edges? This bounds the whole adapter surface.
4. **Experiment data of record:** is there any experiment-data catalog, NeXus/HDF5 standardization, or ELN, or does each beamline write local formats? Where does raw imaging data from BL-04 land, and is reconstruction inline or offline?
5. **The booking/identity chain:** what does `info.rrcat.gov.in/beamline` manage (proposals, scheduling, user roles), and what identity/role model would CORA's Trust BC have to read?
6. **Identifier mapping:** confirm the `BL-NN` port scheme for Indus-2 and the technique-named scheme for Indus-1, and how a run-context maps to (ring, beamline, endstation) across the two-ring facility.
7. **Machine facts to fill:** Indus-2 circumference and emittance; per-beamline energy ranges, source types (bend / wiggler / undulator), and detectors, none of which were catalogued publicly.

---

## 8. Source list

**Facility (hardware facts):**
- RRCAT home: https://www.rrcat.gov.in/
- Indus Synchrotron Radiation Facility index: https://www.rrcat.gov.in/technology/accel/isrf_index.html
- Indus-2 beamlines roster: https://www.rrcat.gov.in/technology/accel/srul/beamlines/index.html
- Indus-1 beamlines roster: https://www.rrcat.gov.in/technology/accel/srul/indus1beamline/index.html
- Wikipedia, Indus 2: https://en.wikipedia.org/wiki/Indus_2

**Control system (software facts):**
- Status of Indus-2 Control System (PCaPAC 2014, TCO202): https://proceedings.jacow.org/PCaPAC2014/papers/tco202.pdf
- RRCAT Indus-2 control systems overview: https://www.rrcat.gov.in/technology/accel/indus/acs/i2ControlSystems.html
- RRCAT Indus control SCADA (WinCC OA / PVSS): https://www.rrcat.gov.in/technology/accel/indus/acs/pvss.html
- RRCAT Accelerator Controls & Beam Diagnostics Division: https://www.rrcat.gov.in/technology/accel/indus/acs/index.html
- Software Scenario for Control System of INDUS-2 (ICALEPCS 2005, O3_014): https://epaper.kek.jp/ica05/proceedings/pdf/O3_014.pdf
- Indus-2 Control System, A Closer Perspective (PCaPAC 2012, weib03): https://proceedings.jacow.org/pcapac2012/talks/weib03_talk.pdf

**Beamline experiment control / DAQ (software facts):**
- Data Acquisition and Control Software for Scanning EXAFS Beamline (LabVIEW + EPICS): https://www.researchgate.net/publication/265695020
- Data acquisition and control software for XRD beamline at Indus-2: https://www.osti.gov/biblio/21410315
- Development of data acquisition and control system for diagnostic beamline (LabVIEW): https://www.osti.gov/etdeweb/biblio/22265584

**Data management / user office:**
- Indus beamline online booking / registration portal: https://info.rrcat.gov.in/beamline/

**Internal-only (named, not reachable):** RRCAT Accelerator Control Section internal code (WinCC OA projects, VME/OS-9 API managers, MSIS), per-beamline LabVIEW/EPICS DAQ, and the central MS-SQL machine-parameter database are all RRCAT-internal; none is on the public web.
