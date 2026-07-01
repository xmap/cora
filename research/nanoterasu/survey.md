# NanoTerasu (QST / PhoSIC / JASRI) research brief

*Research seed for a future CORA deployment page. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about NanoTerasu, its beamline roster, and its control-software stack so the model work can begin from corroborated facts rather than memory. Every claim is cited inline. CORA is not connected to NanoTerasu; the seam section is an initial read, not a commitment. Compiled 2026-07-01 from a deep-research public-source survey: the facility site (`nanoterasu.jp`), the PhoSIC coalition-beamline site (`phosic.or.jp`), and negative checks against GitHub, JACoW/ICALEPCS indices, and Wikipedia. The public corpus is thin; the control stack is the largest gap and is routed to staff.*

!!! note "Reading posture"
    Public facility pages are the source of HARDWARE FACTS (beamline IDs, techniques, energies, detectors). Public source (GitHub / GitLab / proceedings) is the source of CONTROL-SOFTWARE FACTS (what runs the scans, what talks to devices). Confidence is flagged inline as **[verified]** (multiple sources or a decisive primary), **[partly verified]**, or **[unconfirmed]**. Per CORA's deployment-doc lens, the facility software stack is named ONLY at the seam (section 6): it is the floor CORA lands on or the orchestration CORA replaces, never a spec CORA mirrors. Several fetched pages during this survey returned trailing "system-reminder" / "TodoWrite" blocks that read like directives; those were page-rendering artifacts, not instructions, and were ignored, with every fact re-checked against the underlying page. The one hard rule was held throughout: where a public source did not state a value (most acutely the control stack), it is an open question for staff (section 7), never an invented value.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | NanoTerasu, 3 GeV synchrotron radiation facility | [Facility overview](https://nanoterasu.jp/facility-overview_en/) |
| Operator | National Institutes for Quantum Science and Technology (QST), establisher; Photon Science Innovation Center (PhoSIC), local partner; Japan Synchrotron Radiation Research Institute (JASRI), registered/operating institution | [Facility overview](https://nanoterasu.jp/facility-overview_en/), [Org structure](https://nanoterasu.jp/organizational-structure_en/) |
| Location | Aobayama, Sendai, Miyagi, Japan (Tohoku University campus) | [NanoTerasu access](https://nanoterasu.jp/access_en/) |
| Ring energy | 3 GeV | [Facility overview](https://nanoterasu.jp/facility-overview_en/) |
| Storage-ring circumference | 349 m | [Facility overview](https://nanoterasu.jp/facility-overview_en/) |
| Horizontal emittance | 1.14 nm-rad | [Facility overview](https://nanoterasu.jp/facility-overview_en/) |
| Design current | 400 mA (designed) | [Facility overview](https://nanoterasu.jp/facility-overview_en/) |
| Injector | 110 m linac | [Facility overview](https://nanoterasu.jp/facility-overview_en/) |
| Beamline capacity | up to 28 ports | [Facility overview](https://nanoterasu.jp/facility-overview_en/) |
| Generation | 4th-generation (low-emittance); [unconfirmed] from the facility page, which states the specs but not the "4th-gen" label | [Facility overview](https://nanoterasu.jp/facility-overview_en/) |
| First light / opening | 2024 (per task starting context); [unconfirmed] no reachable primary page gave an explicit first-light date | [NanoTerasu top](https://nanoterasu.jp/top_en) |

**[partly verified]** NanoTerasu is a 3 GeV low-emittance (1.14 nm-rad, 349 m ring) synchrotron on the Tohoku University Aobayama campus in Sendai, established by QST with PhoSIC as regional coalition partner and JASRI as the registered operating institution. The 1.14 nm-rad emittance is consistent with a 4th-generation MBA-class ring, but the facility overview page states the number, not the generation label, so the "newest 4th-gen ring" framing carries **[unconfirmed]** until a machine page or design report confirms it. It is notably "the first synchrotron radiation facility in Japan to make the experimental hall accessible without a controlled-radiation-area designation" ([NanoTerasu top](https://nanoterasu.jp/top_en)), which is an access/governance fact, not a hardware one.

**CORA hook:** NanoTerasu splits its beamlines into a QST-run *public* tier and a PhoSIC-run *coalition* (coreto) tier with distinct governance and access rules per beamline. That dual-tier proposal/access model is exactly the kind of governance boundary CORA's Trust BC exists to model, and it is a cleaner data-of-record / debrief pitch than at a single-operator facility.

---

## 2. Candidate beamlines

**Source-of-record posture (decides Tier-2): firewalled / not public.** NanoTerasu publishes hardware-fact beamline pages (technique, energy, some detectors) but does **not** publish any per-beamline device configuration with real control handles. There is **no NanoTerasu controls library on public GitHub** (a `search/repositories?q=nanoterasu` returned zero repos, 2026-07-01), no Beacon/dodal/profile-collection analogue, and no reachable device inventory. This is the ALBA / Sirius / SPring-8 posture, not the Diamond / NSLS-II / APS posture. **A Tier-2 device pass is NOT buildable from public source.** Device topology (PV namespaces, controller boxes, motion axes) must come from staff or descriptors; it must not be inferred from a shared base class, because no shared base class is even public here. **[verified]** (negative result: absence corroborated across GitHub, the facility site, and PhoSIC).

What *is* modellable from public source is the **Tier-1 layer**: the roster, techniques, energy ranges, and the identifier scheme, enough to draft a deployment page's non-device sections and to pick the strongest lines. The roster below is the union of the 3 QST public beamlines and the 7 PhoSIC coalition beamlines with public pages; more ports exist (capacity 28) but have no public technique facts yet.

| Beamline | Tier | Technique | Energy | Detectors (where public) | Control source | Source |
| --- | --- | --- | --- | --- | --- | --- |
| BL02U | public (QST) | Ultrahigh-resolution resonant inelastic soft X-ray scattering (RIXS) | soft X-ray [unconfirmed range] | not public | firewalled | [beamline list](https://nanoterasu.jp/beamline-list_en/) |
| BL06U | public (QST) | Nanoscale soft X-ray ARPES (nano SX-ARPES) | soft X-ray [unconfirmed range] | not public | firewalled | [beamline list](https://nanoterasu.jp/beamline-list_en/) |
| BL13U | public (QST) | Nanoscale soft X-ray absorption (nano SX-XAS) | soft X-ray [unconfirmed range] | not public | firewalled | [beamline list](https://nanoterasu.jp/beamline-list_en/) |
| BL07U | coalition (PhoSIC) | RIXS (HORNET) + scanning XPS (NanoESCA) + ARPES/spin-ARPES (SCORPIUS) | 50-2000 eV (horiz. lin. pol.) | flux >1e12 ph/s; no detector named | firewalled | [BL07U](https://www.phosic.or.jp/equipment/BL07U/e/info_BL07U.html) |
| BL08U | coalition (PhoSIC) | Soft X-ray XAS + XPS; AP-XPS; operando SX-XAFS | 180-2000 eV | TEY / partial-fluorescence-yield modes | firewalled | [BL08U](https://www.phosic.or.jp/equipment/BL08U/e/info_BL08U.html) |
| BL08W (XRD / XAFS / SAXS branches) | coalition (PhoSIC) | Powder XRD, 2D mapping, in-situ; XAFS; SAXS | 17.5 keV or 28.5 keV (XRD) | Hamamatsu C14406DK-2918 flat panel; SDD XSDD30 | firewalled | [BL08W-XRD](https://www.phosic.or.jp/equipment/BL08W_XRD/e/info_BL08W_XRD.html) |
| BL09U | coalition (PhoSIC) | HAXPES + macromolecular crystallography end station (MX-ES) | 5-15 keV (HAXPES fixed 6 keV) | Scienta Omicron electron analyzer | firewalled | [BL09U](https://www.phosic.or.jp/equipment/BL09U/e/info_BL09U.html) |
| **BL09W** | coalition (PhoSIC) | **White-beam wide-field CT, white-beam micro-CT, 4D-CT** | white beam 4-30 keV (peak ~20 keV); flux ~3.0e16 cps (calculated, per page) | Hamamatsu C16240-20UP CMOS; LuAG:Ce 0.2 mm scintillator; 4.6 um px | firewalled | [BL09W](https://www.phosic.or.jp/equipment/BL09W/e/info_BL09W.html) |
| **BL10U** | coalition (PhoSIC) | **Monochromatic micro-CT**, USAXS, XPCS, X-ray ptychography | 2.1-18.3 keV (CT 6-18.3 keV, typ. 8.3 / 15) | Hamamatsu AA-51 / ORCA-Flash 4.0, ~0.5 um detector px (0.65 um CT-measured); ~1 um res, 1801 proj / 180 deg | firewalled | [BL10U](https://www.phosic.or.jp/equipment/BL10U/e/info_BL10U.html) |
| BL14U | coalition (PhoSIC) | Soft X-ray XAS + XMCD; STXM / soft X-ray microscopy | 200-1400 eV (focused 600-1400) | transmission + TEY; focus <=100 nm; 8 T field | firewalled | [BL14U](https://www.phosic.or.jp/equipment/BL14U/e/info_BL14U.html) |

**Strongest next picks for CORA's growth ladder (imaging/tomography-leaning):**

1. **BL10U (monochromatic micro-CT + USAXS + XPCS + ptychography)** is the closest analogue to the APS 2-BM -> FXI imaging pilots: monochromatic tomography with a rotation-stage + area-detector fly/step model CORA already reasons about (1801 projections over 180 deg, ~1 um). It also carries ptychography and XPCS, exercising CORA's coherent-imaging modeling beyond straight CT. **Best single pick.**
2. **BL09W (white-beam wide-field / micro / 4D-CT)** is a white-beam tomography line, complementary to BL10U's monochromatic CT, and 4D-CT stresses the time-resolved-series modeling that 2-BM's dynamic scans motivated. Second pick; together with BL10U it gives two distinct tomography contrast modes at one facility.
3. BL08W-XRD (powder XRD, in-situ / operando) is a reuse-and-reinforce pick that generalizes CORA beyond imaging, but earns no new Family.

The soft-X-ray photoemission/RIXS cluster (BL02U, BL06U, BL07U, BL13U, BL08U, BL14U) is rich but off CORA's tomography ladder; it is where a *photoemission* modeling axis would eventually be earned (twin of NSLS-II ESM / Diamond I05), not a first pick.

**Every value above is a published hardware-page fact (source-backed, not inferred); `confirm` here means "verify currency with staff," a lower bar than the genuinely `[unconfirmed]` control stack in section 3. No PV, controller, or device handle appears here because none is public.**

**Identifier-scheme note.** NanoTerasu names beamlines `BL<nn><letter>` where the letter encodes the source type: `U` = undulator, `W` = wiggler/white-beam (BL08W, BL09W), and the same port can fan into named branches (BL08W splits into XRD / XAFS / SAXS branch stations; BL07U into HORNET / NanoESCA / SCORPIUS). This differs from the APS `sector.station` scheme the pilot assumes on two axes: the source-type letter is part of the identifier, and a single `BL` port hosts multiple co-equal branch endstations. Both are descriptor / identifier-scheme differences to model, not hardware differences. **[verified]** (from the beamline-page URL scheme and branch listings).

---

## 3. Control-system stack, by layer

The control stack is the single largest public-source gap for this facility. No reachable page, repo, or proceedings paper names the beamline control framework, the scan engine, or the DAQ chain. What follows separates the little that is inferable from what is genuinely unknown; the unknowns are routed to section 7, not filled with plausible values.

### Device IO (the floor)

**[unconfirmed].** No public source names the device-IO layer (EPICS IOCs, Tango device servers, or an in-house substrate). JASRI operates NanoTerasu and also operates SPring-8, whose accelerator control is the in-house **MADOCA** framework (not EPICS); this makes a MADOCA-lineage accelerator floor a *reasonable hypothesis* for NanoTerasu, but no fetchable NanoTerasu source states it, so it is flagged **[unconfirmed]** and asked of staff rather than asserted. SPring-8's beamline side has historically used a mix distinct from its accelerator MADOCA; whatever NanoTerasu chose for beamlines is not public. This must not be inferred into a device model.

### Scan orchestration (the seam layer)

**[unconfirmed].** The high-level scan / alignment engine (whether a bluesky/queueserver stack, a MADOCA-based sequencer, or a home-grown per-beamline tool) is not documented in any reachable public source. This is the layer CORA's EdgeConductor would replace or drive through, so it is the highest-value staff question (section 7, Q2).

### Fast paths and exceptions

**[unconfirmed].** Nothing public on triggering, fly-scan hardware, or detector backends. BL10U (1801 projections / 180 deg mono CT) and BL09W (4D-CT) almost certainly run a hardware-triggered continuous-rotation fly-scan, which would widen the ControlPort surface beyond a simple step-scan floor, but the trigger substrate is not public. Ask staff.

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| (none found on public GitHub / GitLab) | no NanoTerasu controls library, device support, or scan engine is public | GitHub `search/repositories?q=nanoterasu` -> 0 repos (2026-07-01) |
| `nanoterasu.jp` (QST) | hardware-fact facility + public-beamline pages | [nanoterasu.jp](https://nanoterasu.jp/top_en) |
| `phosic.or.jp` (PhoSIC) | hardware-fact coalition-beamline pages | [phosic.or.jp](https://www.phosic.or.jp/) |
| `user.nanoterasu.jp` (JASRI) | user-office / proposal portal (governance, not device source) | [user portal](https://user.nanoterasu.jp/?lang=en) |

**Why a full device model is NOT integrity-buildable from public source.** There is no public per-beamline device list with real handles, and no public controls repository of any kind. A GitHub org search returns zero NanoTerasu repositories; Wikipedia has no dedicated article (only a row in the facilities list); the ICALEPCS 2021/2023/2025 institute indexes reachable here surface no NanoTerasu/QST beamline-control paper. Because the device source is firewalled/absent, the entire device topology is routed to the staff questions (section 7). Inference from a presumed MADOCA or EPICS base class is explicitly out of bounds: no such base class is public, and inference is not source. **[verified]** as a negative result.

---

## 5. Data management

**[unconfirmed].** No public source surfaced NanoTerasu's data catalog, file-format policy (NeXus / HDF5), user-office ingestion trigger, or archive chain. The JASRI-operated `user.nanoterasu.jp` portal is the proposal / user-office surface (the governance seam), but its data-of-record posture is not documented publicly. Given JASRI's role, a SPring-8-adjacent data pipeline is plausible but **[unconfirmed]**; it is asked of staff (Q3). This matters because any facility catalog is a source-of-truth contest for the "system of record for the experiment" territory CORA claims; the contest cannot be scoped until the catalog is named.

---

## 6. The CORA seam (initial read)

First pass, not a committed seam. Applies the 2-BM / FXI lens: device IO is the floor CORA never replaces; the higher scan / orchestration layer is where CORA replaces or drives through; the facility catalog is a source-of-truth contest, not a dependency. Because the control stack is [unconfirmed], this read is more provisional than the Sirius or Diamond seams and cannot be locked without the section-7 answers.

**Where the floor stays the floor (drive through, never CORA).** Whatever device-IO substrate NanoTerasu runs (MADOCA-lineage or EPICS, both hypotheses, both [unconfirmed]) is the floor CORA's ControlPort actuates *through*, never owns. If it is EPICS, the APS-pilot ControlPort model carries over directly. If it is MADOCA (JASRI/SPring-8 lineage), a new control substrate adapter must be built behind the existing ControlPort abstraction, which is the port's whole point but is a real cost to budget. Deciding which is Q1 and gates the port-reuse assumption.

**What CORA replaces (edge orchestration).** The scan / alignment engine (unidentified) is the layer CORA's EdgeConductor would conduct over, incrementally and routine-by-routine, on the imaging lines first (BL10U mono CT, BL09W white/4D CT). Whatever engine exists is DATA to learn from, not a spec to mirror; CORA is pitched on governance, replayability, and recipe-binding of tomography routines, never on out-executing the existing engine on speed. Until the engine is named (Q2), the replace-vs-drive-through choice cannot be made.

**Source-of-truth contest (data).** The JASRI data catalog / user-office chain is unidentified (section 5). CORA stays the system of record for the experiment and brings its own PG event store; the facility catalog is named only at the seam, either inverted (fed downstream) or projected into, with the decision deferred until a NanoTerasu deployment that must publish into it is in scope.

**Coexist.** The `user.nanoterasu.jp` proposal / scheduling / identity chain is read, not replaced (Trust BC maps onto it, especially the distinctive public-vs-coalition dual-tier access model). Reconstruction compute for CT (BL09W / BL10U volumes) is a ComputePort roundtrip CORA governs but does not own. The archive is an egress destination; any logbook is subsumed at the debrief layer.

---

## 7. Open questions (for facility staff)

These could not be settled from public sources and need operator confirmation before any seam lock. Contact: QST NanoTerasu Center / JASRI NanoTerasu Research Center (per [org structure](https://nanoterasu.jp/organizational-structure_en/); no individual named publicly).

1. **Device-IO floor:** Is the beamline control substrate EPICS, MADOCA (SPring-8/JASRI lineage), or something else? This decides whether the APS-pilot ControlPort model carries over or a new control-substrate adapter is needed.
2. **Scan orchestration:** What runs the scans and alignment routines per beamline (a bluesky/queueserver stack, a MADOCA sequencer, a home-grown tool), and is it uniform facility-wide or per-beamline? This is the replace-vs-drive-through boundary for CORA's EdgeConductor.
3. **Data of record:** What is the data catalog / user-office ingestion chain, the file-format policy (NeXus application definitions, e.g. NXtomo for BL09W/BL10U?), and where does raw data land? Is ingestion mandatory, and at what point?
4. **Per-beamline device inventory:** For the imaging picks BL10U and BL09W first: PV/handle namespaces, controller boxes, motion axes (rotation stage, sample positioners), and the fly-scan trigger substrate. None of this is public.
5. **Fast paths:** Do BL10U (mono CT, 1801 proj) and BL09W (4D-CT) run hardware-triggered continuous-rotation fly-scans, and on what trigger/timing hardware? This bounds the ControlPort surface beyond step-scan.
6. **Governance mapping:** How do the public (QST) vs coalition (PhoSIC) beamline tiers differ in proposal, access, and role model, and how should CORA's Trust BC map onto that dual-tier structure and the JASRI user portal?
7. **Roster + identifiers:** Confirm the authoritative operating-beamline list (public capacity is 28 ports; 10 have public pages), and the `BL<nn><U|W>` + named-branch identifier scheme, so the descriptor's identifier model matches the facility's.
8. **Facility framing:** Confirm the 4th-generation classification and the first-light / regular-operations date, neither of which a reachable primary page stated explicitly.

---

## 8. Source list

**Facility (hardware facts):**
- NanoTerasu top: https://nanoterasu.jp/top_en
- Facility overview (ring specs, capacity): https://nanoterasu.jp/facility-overview_en/
- Mechanism: https://nanoterasu.jp/mechanism_en/
- Organizational structure (QST / PhoSIC / JASRI roles): https://nanoterasu.jp/organizational-structure_en/
- Public beamline list (BL02U / BL06U / BL13U): https://nanoterasu.jp/beamline-list_en/
- Facility results / publications: https://nanoterasu.jp/facility-results_en/
- Access (Sendai / Tohoku Aobayama): https://nanoterasu.jp/access_en/
- User portal (JASRI, proposal / user office): https://user.nanoterasu.jp/?lang=en

**Coalition (coreto) beamlines (PhoSIC, hardware facts):**
- PhoSIC home: https://www.phosic.or.jp/
- PhoSIC beamline map (EN): https://www.phosic.or.jp/equipment/index_e.html
- BL07U (RIXS / XPS / ARPES): https://www.phosic.or.jp/equipment/BL07U/e/info_BL07U.html
- BL08U (soft X XAS / XPS / AP-XPS): https://www.phosic.or.jp/equipment/BL08U/e/info_BL08U.html
- BL08W-XRD: https://www.phosic.or.jp/equipment/BL08W_XRD/e/info_BL08W_XRD.html
- BL08W-XAFS: https://www.phosic.or.jp/equipment/BL08W_XAFS/e/info_BL08W_XAFS.html
- BL08W-SAXS: https://www.phosic.or.jp/equipment/BL08W_SAXS/e/info_BL08W_SAXS.html
- BL09U (HAXPES / MX-ES): https://www.phosic.or.jp/equipment/BL09U/e/info_BL09U.html
- BL09W (white-beam CT / micro-CT / 4D-CT): https://www.phosic.or.jp/equipment/BL09W/e/info_BL09W.html
- BL10U (mono micro-CT / USAXS / XPCS / ptychography): https://www.phosic.or.jp/equipment/BL10U/e/info_BL10U.html
- BL14U (soft X XAS / XMCD / STXM): https://www.phosic.or.jp/equipment/BL14U/e/info_BL14U.html

**Control system (software facts):**
- None found. No public NanoTerasu controls repository on GitHub (`search/repositories?q=nanoterasu` -> 0 results, 2026-07-01). No NanoTerasu/QST beamline-control paper surfaced in the reachable ICALEPCS 2021 / 2023 / 2025 institute indexes. Control stack is a staff question (section 7, Q1-Q2, Q4-Q5).

**Data management:**
- None found publicly. Data catalog / format policy is a staff question (section 7, Q3).

**Negative / corroborating checks:**
- Wikipedia: no dedicated NanoTerasu article; only a row in https://en.wikipedia.org/wiki/List_of_synchrotron_radiation_facilities

**Internal-only or unreachable:** No internal VCS host was named in public source (unlike Sirius `gitlab.cnpem.br` or MAX IV `gitlab.maxiv.lu.se`); the control source is simply not surfaced publicly at all, which is a stronger firewall than a named-but-unreachable host.
