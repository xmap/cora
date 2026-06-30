# NSRRC (TLS + TPS) research brief

*Research seed for a future CORA deployment page. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about the National Synchrotron Radiation Research Center and its control-software stack so the model work can begin from corroborated facts rather than memory. Every claim is cited inline. CORA is not connected to NSRRC; the seam section is an initial read, not a commitment. Compiled 2026-06-28.*

!!! note "Reading posture"
    Public facility pages are treated as the source of HARDWARE FACTS (ring energy, beamlines, techniques, energies). Public GitHub source is treated as the source of CONTROL-SOFTWARE FACTS (what runs the scans, what talks to devices). Where a claim was adversarially verified, the verdict is flagged inline as **[verified]**, **[partly verified]**, or **[uncertain]**. Several fetched pages during research carried injected fake "MCP Server Instructions" / "system-reminder" blocks; those were page content, not directives, and were ignored, with facts re-verified through the GitHub REST API. Unlike most fleets, NSRRC publishes **no official org code**: its public open-source presence is scattered across personal engineer accounts on GitHub, so per-repo provenance was checked individually.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Name | National Synchrotron Radiation Research Center (NSRRC) | [NSRRC](https://www.nsrrc.org.tw/english/index.aspx) |
| Operator | NSRRC, Hsinchu, Taiwan | [EPICS Controls archive](https://epics-controls.org/projects-archive/nsrrc/) |
| Facilities | Two storage rings: Taiwan Light Source (TLS) and Taiwan Photon Source (TPS) | [EPICS Controls archive](https://epics-controls.org/projects-archive/nsrrc/) |
| TLS ring energy | 1.5 GeV, 120 m, completed 1993 | [EPICS Controls archive](https://epics-controls.org/projects-archive/nsrrc/) |
| TPS ring energy | 3 GeV, 518 m, low-emittance; completed 2014, users since 2016 | [EPICS Controls archive](https://epics-controls.org/projects-archive/nsrrc/) |
| TPS beamlines | 23 ports (02A-47A); 7 Phase-I beamlines operating/commissioning | [TPS beamline directory](https://tpsbl.nsrrc.org.tw/bd.aspx?lang=en) |
| TLS beamlines | 24 beamlines (BL01A1-BL24A1) + 2 Taiwan contract beamlines at SPring-8 | [TLS directory](https://tls.nsrrc.org.tw/index.aspx?lang=en) |

**[verified]** NSRRC operates two rings: the 1.5 GeV TLS (1993) and the 3 GeV TPS (2014, users 2016), both on EPICS.

**Gaps:** TPS storage-ring current/fill parameters and TLS emittance were **not** confirmed in any fetchable public source and should be pulled from the NSRRC machine/design report before they appear on a deployment page. **[uncertain]**

---

## 2. Beamline catalog

The seven TPS Phase-I beamlines with public source/energy/status facts, plus the named endstations that have public software (the modelling candidates). Energies and techniques are from the TPS per-port directory; software-bearing endstations trace to GitHub repos. No beamlines invented.

| Port | Technique | Energy | Source ID | Status | Reference |
| --- | --- | --- | --- | --- | --- |
| 05A | Protein microcrystallography (MX) | 5.7-20 keV | IU22 | Operating | [dir](https://tpsbl.nsrrc.org.tw/bd.aspx?lang=en), [SPXF](https://nsrrcspxf.github.io/nsrrcspxf/index.html) |
| 07A | Micro-focus protein crystallography (MX) | 6-20 keV | IU22 | Operating | [dir](https://tpsbl.nsrrc.org.tw/bd.aspx?lang=en), [SPXF](https://nsrrcspxf.github.io/nsrrcspxf/index.html) |
| 09A | Temporally coherent X-ray diffraction | 5.6-25 keV | IU22 | Operating | [dir](https://tpsbl.nsrrc.org.tw/bd.aspx?lang=en) |
| 19A | High-resolution powder XRD + PDF | up to ~20 keV | - | Operating | [2019 AsCA poster](https://tpsbl.nsrrc.org.tw/userdata/upload/19A/PDF/2019AsCA_poster_BHChen.pdf) |
| 21A | X-ray nanodiffraction | 5-30 keV white / 7-25 keV mono | IUT22-3m | Operating | [dir](https://tpsbl.nsrrc.org.tw/bd.aspx?lang=en) |
| 23A | X-ray nanoprobe | 4-15 keV | IU22 | Under construction | [dir](https://tpsbl.nsrrc.org.tw/bd.aspx?lang=en) |
| 25A | Coherent X-ray scattering | 5.5-20 keV | IU22 | Operating | [bd_page 25A](https://tpsbl.nsrrc.org.tw/bd_page.aspx?lang=en&pid=1037&port=25a) |
| 31A | Diffraction + absorption | DCM energy series | - | Operating | [diff](https://github.com/tarranchen/script_generator_diff) |
| 32A | Tender X-ray absorption spectroscopy (TXAS) | 1.7-11 keV | bending magnet | Operating | [Liang et al. 2025](https://web.nsrrc.org.tw/upload/J10660.pdf) |
| 39A | Nano-ARPES | soft X-ray | - | Operating | [IOP 2025](https://iopscience.iop.org/article/10.1088/1742-6596/3010/1/012112) |
| 41A | Soft X-ray scattering (RIXS) | 400-1200 eV | Tandem EPU48 | Commissioning | [bd dir](https://tpsbl.nsrrc.org.tw/bd.aspx?lang=en), [RIXS_41A](https://github.com/BlenderCN-Org/RIXS_41A) |
| 45A | Submicron soft X-ray spectroscopy | 280-1500 eV | EPU46 | Operating | [dir](https://tpsbl.nsrrc.org.tw/bd.aspx?lang=en) |

TLS-side, only **BL01B** (transmission X-ray microscopy / tomography) and the MX endstation **TLS 15A1** (biopharmaceutical protein crystallography, Rayonix MX300HE CCD + SAM auto-mounter) have public software traces ([TXM toolbox](https://github.com/JieChungChen/BL01B_TXM_ToolBox), [SPXF](https://nsrrcspxf.github.io/nsrrcspxf/index.html)).

**MX cluster:** NSRRC's three MX endstations share sources/detectors/robots across both rings: **TPS 07A** (EIGER2 X 16M, ISARA), **TPS 05A** (EIGER2 X 9M, ISARA), **TLS 15A1** (MX300HE, SAM) ([SPXF overview](https://nsrrcspxf.github.io/nsrrcspxf/index.html)). **[verified]**

**Status caveat [uncertain]:** the full 23-port TPS list (02A, 05A, 07A, 09A, 13A, 15A, 19A, 20A, 21A, 23A, 24A, 25A, 27A, 31A, 32A, 35A, 38A, 39A, 41A, 43A, 44A, 45A, 47A) is confirmed, but per-port status for the ~16 ports without public software should be re-confirmed with staff.

---

## 3. Control-system stack, by layer

NSRRC runs a single **EPICS-based control floor across both rings**, but there is **no facility-wide beamline scan framework** the way Sirius has sophys or Diamond has dodal. Each beamline carries its own bespoke acquisition layer over the shared EPICS floor. The accelerator and beamline EPICS domains are separate, joined at a gateway IOC.

### Device IO / EPICS (the floor)

- **EPICS** is the control-system foundation at both accelerator and beamline level. **[verified]** ([EPICS Controls archive](https://epics-controls.org/projects-archive/nsrrc/))
- The control plane is dated and quantified: **>200 EPICS IOCs, ~10^5 PVs, EPICS 3.14.12.x (32-bit)** as of 2017, with a v7 migration under study ([ICALEPCS 2017 THPHA065](https://proceedings.jacow.org/icalepcs2017/papers/thpha065.pdf)). **[verified]**
- Accelerator/beamline seam: beamline and endstation control environments are separate EPICS domains; the integration point is a **beamline-rack EPICS IOC carrying an EVR (MRF event timing) plus a co-located gateway**. **[verified]** ([ICALEPCS 2017 THPHA065](https://proceedings.jacow.org/icalepcs2017/papers/thpha065.pdf))
- Beamline device IO uses standard EPICS records over Channel Access. The 41A RIXS repo exposes a concrete per-beamline PV grammar (`41a:` prefix; AGM/AGS energy, xyz/hexapod/goniometer motors with `.VAL/.RBV/.MOVN/.STOP`, CCD + I0/Iph/TEY signals) ([RIXS_41A pvlist.py](https://github.com/BlenderCN-Org/RIXS_41A)). 07A uses `07a:` / `07a-ES:` PV prefixes plus EPICS motor records ([NSRRC_TPS07A](https://github.com/light911/NSRRC_TPS07A)). **[verified]**
- Front-end / accelerator devices wrap commercial hardware behind EPICS: Yokogawa e-RT3/F3RP70 PLC -> EPICS soft-IOC for vacuum/masks/slits/interlocks ([NSRRC-Yokogawa-EPICS](https://github.com/Yu-Zheng/NSRRC-Yokogawa-EPICS)); Galil DMC controllers for motion ([TPS_XBPM_2D_Scan](https://github.com/Yu-Zheng/TPS_XBPM_2D_Scan)); an in-house EtherCAT stepper-motor controller, NEMC, with EPICS support in development ([NEMC](https://github.com/nsrrcnemc-pixel/NEMC)).

### Orchestration + scan engine (the seam layer)

The orchestration layer is **per-beamline and heterogeneous**. Three distinct patterns are publicly documented and should be modelled deliberately, not blended:

1. **BLU-ICE/DCSS + EPICS (MX, TPS 07A).** Acquisition is orchestrated through a DCSS server (Blu-Ice/SSRL lineage) reached via an EPICS Device Handler Server (DHS); EPICS is used for flux/beam-size lookup tables, the MD3 diffractometer, EIGER2, and the ISARA robot. The Meshbest repo adds the mesh-scan + analysis flow (Eiger via ZMQ, migrating to DESY ASAP::O; Dozor + CHiMP ML) ([NSRRC_TPS07A](https://github.com/light911/NSRRC_TPS07A), [TPS07A-Meshbest](https://github.com/light911/TPS07A-Meshbest)). **[verified]**
2. **Pure EPICS + PyQt5 + custom CLI/macro (RIXS, TPS 41A).** The "Blue Magpie" GUI maps PVs to a `mv/mvr/scan/xas/tscan/rixs` command grammar over a QThread scan engine, with a `safeflags` device-arming gate and HDF5 output ([RIXS_41A](https://github.com/BlenderCN-Org/RIXS_41A)). **[verified]**
3. **CSS-admin + LabVIEW-user + Keyence-PLC fly-scan (TXAS, TPS 32A).** Two-tier control: Control System Studio for operators (PV-based, implies EPICS), a LabVIEW GUI for general users; in-house scans only (slit/energy/spectral/Universal, step + fly); fly-scan on a Keyence KV-8000 PLC ([Liang et al. 2025](https://web.nsrrc.org.tw/upload/J10660.pdf)). **[partly verified]** (OCR-recovered; EPICS underlies the CSS tier by implication, not statement)

Edge patterns (not core): EPICS + SPEC + Python with named per-detector routines (`mscan_py`, `pdfscan`, `MCAscan`, `PEscan`) at HRPXRD 19A ([2019 AsCA poster](https://tpsbl.nsrrc.org.tw/userdata/upload/19A/PDF/2019AsCA_poster_BHChen.pdf)); offline script generators emitting flat-text command scripts at 31A ([diff](https://github.com/tarranchen/script_generator_diff), [absorb](https://github.com/tarranchen/script_generator_absorb)); ad-hoc Python step loops (move -> sleep -> caget -> store) for XBPM scans ([TPS_XBPM_2D_Scan](https://github.com/Yu-Zheng/TPS_XBPM_2D_Scan)). **No Bluesky / Ophyd / Sardana / Tango anywhere in the public corpus.** **[partly verified]** (absence across the repos read; not an exhaustive negative)

### GUI

- Operator GUIs are built on **Control System Studio (CS-Studio)** (EDM + MATLAB + CSS per the 2017 ops paper); both thick-client RCP and browser RAP variants were packaged ([chiijung/org.csstudio.nsrrc.product](https://github.com/chiijung/org.csstudio.nsrrc.product), [ICALEPCS 2017 THPHA065](https://proceedings.jacow.org/icalepcs2017/papers/thpha065.pdf)). The public CS-Studio repos are ~2015-era and partly demo-template (alarm root still `demo`, authorization wide-open `.*`); the current operator stack (legacy CS-Studio vs Phoebus) is **unconfirmed**. **[uncertain]**
- Per-beamline scientific GUIs are bespoke PyQt5 desktop apps (41A "Blue Magpie", 07A Meshbest client-server) ([RIXS_41A](https://github.com/BlenderCN-Org/RIXS_41A), [TPS07A-Meshbest](https://github.com/light911/TPS07A-Meshbest)).
- MX beamlines: **NSRRC is a formal MXCuBE collaboration partner**, listed alongside ESRF, SOLEIL, MAX IV, DESY, ALBA, Elettra, ANSTO in the MXCuBE-Web README ([mxcube/mxcubeweb](https://github.com/mxcube/mxcubeweb)). **[verified]** Whether the MX cluster (07A/05A/15A1) currently runs MXCuBE-Web in production, alongside or replacing the BLU-ICE/DCSS path, is a key open question.

### Data acquisition + formats

- Formats span the spectrum: HDF5/NeXus + CBF + TIFF + ALBULA from the EIGER2 stream (07A); HDF5 from the 41A RIXS engine; Xradia/Zeiss `.txrm`/`.xrm` OLE files (BL01B TXM); CSV/flat text (XBPM, 32A PV params, Athena-compatible XAS output). **No facility-wide raw-data container or NeXus standardization layer** is visible publicly. **[partly verified]**
- Archive/alarm/logbook (TPS, from CS-Studio config + 2017 ops paper): **BEAUTY** (CSS archiver on PostgreSQL), **BEAST** alarms (CS-Studio on MySQL/ActiveMQ), **ChannelFinder** directory, **Olog** logbook. ([chiijung/org.csstudio.nsrrc.product](https://github.com/chiijung/org.csstudio.nsrrc.product), [ICALEPCS 2017 THPHA065](https://proceedings.jacow.org/icalepcs2017/papers/thpha065.pdf)) **[partly verified]** (config is ~2015-era)
- No facility-wide ICAT-style metadata catalog was found in either survey round. **[uncertain]**

---

## 4. Where the code lives

There is **no official NSRRC GitHub org with public content**: both `github.com/NSRRC` and `github.com/nsrrc` exist with **zero public repositories**, and the `nsrrc` topic is unused. **[verified]** All usable public code lives in personal/engineer accounts. Repo facts from live GitHub API (2026-06-28).

| Repo | Role | Language | Health |
| --- | --- | --- | --- |
| [light911/NSRRC_TPS07A](https://github.com/light911/NSRRC_TPS07A) | **Primary modelling target.** Production-style MX endstation control/DAQ (MD3, EIGER2, ISARA, DCSS/DHS, file writers, auto-processing) | Python | Active; 2021 -> 2025-12; ~217 files; GPL-3.0; **code on `master`**, not `main` |
| [light911/TPS07A-Meshbest](https://github.com/light911/TPS07A-Meshbest) | 07A MX mesh-scan + acquisition (Eiger/ASAP::O, Dozor, CHiMP, PyQt5 client-server) | Python | Active to 2025-12; no license/README |
| [BlenderCN-Org/RIXS_41A](https://github.com/BlenderCN-Org/RIXS_41A) | **PV-grammar reference.** TPS 41A RIXS control GUI; full `41a:` PV map + CLI/macro grammar | Python (PyQt5) | Single-author; HDF5 output |
| [Yu-Zheng/NSRRC-Yokogawa-EPICS](https://github.com/Yu-Zheng/NSRRC-Yokogawa-EPICS) | Front-end PLC -> EPICS soft-IOC bridge (vacuum/masks/slits/interlocks) | Python/Shell | Single commit |
| [Yu-Zheng/TPS_XBPM_2D_Scan](https://github.com/Yu-Zheng/TPS_XBPM_2D_Scan) | Front-end XBPM 2D raster (Galil + EPICS CA, CSV out) | Python | Abandoned 2017 |
| [tarranchen/script_generator_diff](https://github.com/tarranchen/script_generator_diff) / [_absorb](https://github.com/tarranchen/script_generator_absorb) | TPS 31A scan-script generators | Python / VB.NET | Low activity |
| [TPS19A/ADTools](https://github.com/TPS19A/ADTools) / [GSASIIPatch](https://github.com/TPS19A/GSASIIPatch) | 19A areaDetector tooling + GSAS-II patches | Python | Active |
| [nsrrcspxf/nsrrcspxf](https://github.com/nsrrcspxf/nsrrcspxf) | Static SPXF MX site/manual (TLS15A, TPS05A, TPS07A) | HTML/CSS | 1000+ commits |
| [nsrrcnemc-pixel/NEMC](https://github.com/nsrrcnemc-pixel/NEMC) | In-house EtherCAT stepper-motor controller; EPICS support in dev | LabVIEW | 35 commits; MIT |
| [chiijung/org.csstudio.nsrrc.*](https://github.com/chiijung/org.csstudio.nsrrc.product) | CS-Studio operator-desktop packaging (RCP + RAP) | Java | Dead since 2015 |
| [JieChungChen/BL01B_TXM_ToolBox](https://github.com/JieChungChen/BL01B_TXM_ToolBox), [TXM_Tomography_Package](https://github.com/JieChungChen/TXM_Tomography_Package) | TLS BL01B TXM offline reconstruction/processing | Python | Active to 2025 |
| [github-ywtsai/PyPtycho](https://github.com/github-ywtsai/PyPtycho), [PyCDI](https://github.com/github-ywtsai/PyCDI) | Coherent-imaging reconstruction (offline); commits resolve to `srrcnt.org.tw` (NSRRC legacy domain) | Python | Active to 2025 |

**Non-GitHub hosts: confirmed absent.** GitLab (`gitlab.com/nsrrc`, self-hosted `gitlab.nsrrc.org.tw`/`git.nsrrc`), Bitbucket, and SourceForge were probed in English + Chinese with `site:` filters across multiple angles and returned zero results. Any NSRRC GitLab is internal/firewalled and not web-indexed. **[verified]** as web-reachable; an internal GitLab cannot be ruled out.

**Institutional document registry (not a VCS):** `web.nsrrc.org.tw/upload/C0xxxx.pdf` and `J1xxxx.pdf` hold control-config papers and journal mirrors (e.g. the Tender-XAS paper `J10660.pdf`); worth periodic sweeping. **[verified]**

**GitHub code-search (authenticated `gh`, 2026-06-28):** PV-grammar queries `"07a:" caget` and `"41a:" epics` returned **zero** hits across public GitHub, confirming those grammars exist only in the two repos above; no hidden beamline tree leaks its PV namespace. The repo set above is the complete public NSRRC beamline-code corpus. **[verified]**

---

## 5. Data management + processing

- **No facility-wide data-of-record or standardization engine** is publicly visible (contrast Sirius's Assonant/NeXus direction). Each beamline writes its detector-native format. **[partly verified]**
- **MX (07A):** on-the-fly processing bundles DIALS, yamtbx, cctbx, XDS, Pointless; data staging RAM-disk -> NFS -> HTTP; HDF5/NeXus from the EIGER2 stream ([NSRRC_TPS07A](https://github.com/light911/NSRRC_TPS07A)). The Meshbest path adds Dozor (spot-finding) and CHiMP (ML crystal detection), with the Eiger acquisition channel migrating from ZMQ to DESY **ASAP::O** ([TPS07A-Meshbest](https://github.com/light911/TPS07A-Meshbest)). **[verified]**
- **TXM (BL01B):** offline reconstruction via Astra Toolbox + PyTorch (FBP/ML-EM) plus a DDPM/DDIM diffusion background remover ([TXM_Tomography_Package](https://github.com/JieChungChen/TXM_Tomography_Package), [BackgroundRemoverAI](https://github.com/JieChungChen/NSRRC-BL01B-TXM-BackgroundRemoverAI)). **[verified]**
- **HRPXRD (19A):** analysis via GSAS-II (with in-house patches), PDFgetX3 / xPDFsuite ([2019 AsCA poster](https://tpsbl.nsrrc.org.tw/userdata/upload/19A/PDF/2019AsCA_poster_BHChen.pdf), [TPS19A/GSASIIPatch](https://github.com/TPS19A/GSASIIPatch)).
- **Coherent imaging:** ptychography/CDI reconstruction in PyPtycho/PyCDI (offline, NSRRC-authored) ([github-ywtsai](https://github.com/github-ywtsai/PyPtycho)).
- **No public HPC cluster description** was found (contrast Sirius's TEPUI); compute appears beamline-local. **[uncertain]**

---

## 6. The CORA seam (initial read)

This is a first pass, not a committed seam. It applies the same 2-BM / FXI / Sirius lens: EPICS and device IO are the floor CORA never replaces; the higher scan/orchestration layer is where CORA replaces or drives through.

**Where EPICS stays the floor.** All NSRRC beamline device IO is EPICS records over Channel Access, with commercial hardware (Yokogawa PLC, Galil, MD3, EIGER2, ISARA) wrapped behind PVs. CORA's ControlPort would actuate **through** this EPICS floor exactly as at 2-BM and FXI; CORA never owns PVs, IOCs, or the device layer. The accelerator-side EPICS stack and the EVR/MRF timing + PSS/interlock layer are out of scope.

**What CORA would replace or drive through.** Unlike Sirius (one uniform sophys layer), NSRRC's orchestration is **per-beamline and heterogeneous**, so the seam decision is made per pattern rather than facility-wide:

1. **MX (07A) BLU-ICE/DCSS over EPICS** is the direct analog of the 2-BM TomoScan seam: CORA's EdgeConductor would **replace the DCSS scan/alignment orchestration**, conducting the MD3 + EIGER2 + ISARA over the EPICS floor. This is the "edge promoted to intended" posture.
2. **RIXS (41A) pure EPICS + custom CLI** has no external orchestration server: CORA's conduct path would replace the "Blue Magpie" QThread scan engine directly over the `41a:` PV grammar.
3. **TXAS (32A) CSS + LabVIEW + Keyence PLC** is the hardest seam: the LabVIEW user tier and PLC fly-scan are floor CORA drives through, not replaces.

The detector-native files (HDF5/NeXus at 07A, vendor formats elsewhere) are the existing data path; CORA brings its own data of record (PG event store), so these become a **source to subsume**, not a system CORA depends on.

**Open design questions.**
- For the MX cluster, is the live orchestration BLU-ICE/DCSS (as the 07A repos show) or MXCuBE-Web (given the formal MXCuBE partnership)? This determines whether the CORA MX seam matches the 2-BM DCSS pattern or the MX3 / Manaca MXCuBE pattern. **This is the top staff question before MX modelling.**
- Has the 07A Eiger path completed the ZMQ -> ASAP::O migration in production?
- Does EPICS underlie the 32A CSS/LabVIEW tier, as the paper implies but does not state?
- **PSS/interlock: no public source in either survey round exposes PSS detail.** This must come from staff, not inferred from repos.
- The current operator GUI stack (legacy CS-Studio vs Phoebus) is unconfirmed.

---

## 7. Confidence + gaps

**Well-corroborated (multiple primary sources or verified):**
- Facility identity: two rings, TLS 1.5 GeV (1993) + TPS 3 GeV (2014/2016). **[verified]**
- EPICS as the device-IO floor on both rings; >200 IOCs, ~10^5 PVs, EPICS 3.14.12.x (2017). **[verified]**
- Per-beamline heterogeneous orchestration (no facility scan framework); three documented patterns. **[verified]**
- TPS 07A as the most complete public MX control/DAQ tree; 41A as the richest pure-EPICS PV grammar. **[verified]**
- No official public NSRRC GitHub org; all code in personal accounts; no non-GitHub web-reachable host. **[verified]**
- NSRRC as a formal MXCuBE collaboration partner. **[verified]**

**Uncertain or single-source:**
- Per-port status for the ~16 TPS ports without public software. **[uncertain]**
- Current operator GUI stack (CS-Studio vs Phoebus); the public configs are ~2015-era. **[uncertain]**
- 32A EPICS-underlies-CSS (OCR-recovered, implied not stated). **[partly verified]**
- No Bluesky/Ophyd/Sardana/Tango anywhere (absence across repos read, not exhaustive). **[partly verified]**
- No facility-wide data catalog or HPC cluster (consistent absence, not proof). **[uncertain]**
- Internal GitLab existence (cannot be ruled out; not web-reachable). **[partly verified]**

**What to ask facility staff:**
1. TPS ring current/fill parameters and TLS emittance.
2. The live MX orchestration: BLU-ICE/DCSS vs MXCuBE-Web across the 07A/05A/15A1 cluster, and whether 05A/15A1 share 07A's code.
3. Per-beamline device inventory (PV namespaces, controller boxes, motion axes, detectors) for the modelling target(s).
4. 07A Eiger ZMQ -> ASAP::O migration status; whether on-the-fly processing is inline with acquisition.
5. 32A control: does EPICS underlie the CSS tier; how do the CSS-admin and LabVIEW-user tiers split.
6. PSS / interlock implementation at beamline endstations (no public source exposes this).
7. User-office / proposal system, role/permission model (the 07A repo shows LDAP auth at `ldap://10.7.1.1` and a mandatory `safetytraining.nsrrc.org.tw` portal), and any ELN, for the governance seam.
8. Current operator GUI stack (legacy CS-Studio vs Phoebus migration).

---

## 8. Recommended deployment beamline

**Recommendation: TPS 07A (Micro-focus Protein Crystallography) as the first NSRRC deployment, with TPS 41A (RIXS) as a strong second / PV-grammar reference.**

**Why 07A:**

- **It is the only public NSRRC source that supports near-complete reverse-engineering**, the way Diamond's `dodal` and Sirius's `sophys` supported prior pilots. The `NSRRC_TPS07A` + `TPS07A-Meshbest` pair gives a real, maintained, single-beamline tree with an explicit device model (MD3 diffractometer, EIGER2 detector, ISARA robot, slits, attenuators, DBPMs), a concrete `07a:` PV grammar, file-format writers, and a clean control-protocol seam (DCSS/DHS). **[verified]**
- **The seam matches CORA's strongest precedent.** The BLU-ICE/DCSS orchestration over EPICS is the direct analog of the 2-BM TomoScan seam that CORA has already designed against: EPICS stays the floor, CORA's EdgeConductor replaces the DCSS scan/alignment orchestration. The "edge promoted to intended" posture transfers directly.
- **It reuses existing CORA MX vocabulary.** CORA has already modelled MX at Diamond i03, NSLS-II FMX/AMX, and Australian Synchrotron MX3 (the Goniometer Family, MX Methods, autonomous robot sample exchange). TPS 07A's MD3 + EIGER2 + ISARA stack maps onto that vocabulary, so 07A is a **reuse-and-reinforce** deployment, not a from-scratch one.
- **The MXCuBE partnership is a reuse lever.** Because NSRRC is a formal MXCuBE partner, the MX cluster likely shares the same software lineage as MX3 (MXCuBE Exporter) and Sirius Manaca (MXCuBE-Web), so the CORA MX seam may transfer more directly than the raw BLU-ICE repo suggests, pending the staff question above.
- **One device-library generalizes across three endstations and both rings.** The MX cluster (07A / 05A / 15A1) shares sources, detectors, and robots, so modelling 07A first sets up cheap follow-on coverage of 05A and 15A1.

**Why 41A is the recommended second / reference:** it is the richest **pure-EPICS** exemplar found (explicit PV -> command -> scan mapping with a `safeflags` arming gate), complementing 07A's BLU-ICE pattern. It is the best evidence of how an NSRRC beamline maps PVs to a scan engine without an external orchestration server, and would graduate a soft X-ray RIXS technique CORA has not yet modelled.

**Caveats carried into modelling:** both 07A repos are operational working trees (committed `.pyc`/logs/`.bak`, code on `master` not `main`, single contributor, no packaging), so treat them as **data to learn from, not a spec to mirror**, per CORA's intentional-modelling stance. Every physical/control fact above stays `confirm`-pending until backed by a repo read or the beamline team, exactly as the other reverse-engineered pages are framed.

---

## 9. Source list

**Facility (hardware facts):**
- NSRRC: https://www.nsrrc.org.tw/english/index.aspx
- EPICS Controls project archive (NSRRC): https://epics-controls.org/projects-archive/nsrrc/
- TPS beamline directory: https://tpsbl.nsrrc.org.tw/bd.aspx?lang=en
- TPS beamline index: https://tpsbl.nsrrc.org.tw/index.aspx?lang=en
- TPS 25A control page: https://tpsbl.nsrrc.org.tw/bd_page.aspx?lang=en&pid=1037&port=25a
- TLS directory: https://tls.nsrrc.org.tw/index.aspx?lang=en
- SPXF (MX) overview: https://nsrrcspxf.github.io/nsrrcspxf/index.html
- SPXF TPS07A spec: https://nsrrcspxf.github.io/nsrrcspxf/TPS07A.html

**Control software (GitHub, personal/engineer accounts):**
- light911/NSRRC_TPS07A: https://github.com/light911/NSRRC_TPS07A
- light911/TPS07A-Meshbest: https://github.com/light911/TPS07A-Meshbest
- BlenderCN-Org/RIXS_41A: https://github.com/BlenderCN-Org/RIXS_41A
- Yu-Zheng/NSRRC-Yokogawa-EPICS: https://github.com/Yu-Zheng/NSRRC-Yokogawa-EPICS
- Yu-Zheng/TPS_XBPM_2D_Scan: https://github.com/Yu-Zheng/TPS_XBPM_2D_Scan
- tarranchen/script_generator_diff: https://github.com/tarranchen/script_generator_diff
- tarranchen/script_generator_absorb: https://github.com/tarranchen/script_generator_absorb
- TPS19A/ADTools: https://github.com/TPS19A/ADTools
- TPS19A/GSASIIPatch: https://github.com/TPS19A/GSASIIPatch
- nsrrcspxf/nsrrcspxf: https://github.com/nsrrcspxf/nsrrcspxf
- nsrrcnemc-pixel/NEMC: https://github.com/nsrrcnemc-pixel/NEMC
- chiijung/org.csstudio.nsrrc.product: https://github.com/chiijung/org.csstudio.nsrrc.product
- JieChungChen/BL01B_TXM_ToolBox: https://github.com/JieChungChen/BL01B_TXM_ToolBox
- JieChungChen/TXM_Tomography_Package: https://github.com/JieChungChen/TXM_Tomography_Package
- JieChungChen/NSRRC-BL01B-TXM-BackgroundRemoverAI: https://github.com/JieChungChen/NSRRC-BL01B-TXM-BackgroundRemoverAI
- github-ywtsai/PyPtycho: https://github.com/github-ywtsai/PyPtycho
- github-ywtsai/PyCDI: https://github.com/github-ywtsai/PyCDI

**MX collaboration:**
- mxcube/mxcubeweb (NSRRC listed as partner): https://github.com/mxcube/mxcubeweb

**Papers and proceedings:**
- Conceptual Design of the TPS Control System (ICALEPCS 2007 WPPA02): https://epaper.kek.jp/ica07/PAPERS/WPPA02.PDF
- Operation Experiences of the TPS Control System (ICALEPCS 2017 THPHA065): https://proceedings.jacow.org/icalepcs2017/papers/thpha065.pdf
- EPICS vacuum control and safety-interlock for TPS (PCaPAC 2018 WEP14): https://proceedings.jacow.org/pcapac2018/papers/wep14.pdf
- DAQ and reduction at TPS 19A HRPXRD (AsCA 2019 poster): https://tpsbl.nsrrc.org.tw/userdata/upload/19A/PDF/2019AsCA_poster_BHChen.pdf
- Data Acquisition Software for the Tender XAS Beamline at TPS (J. Phys. Conf. Ser. 3010 012121, 2025): https://web.nsrrc.org.tw/upload/J10660.pdf (DOI 10.1088/1742-6596/3010/1/012121)
- Nano-ARPES (TPS 39A) EPICS UI (J. Phys. Conf. Ser. 3010 012112, 2025): https://iopscience.iop.org/article/10.1088/1742-6596/3010/1/012112

**Confirmed-negative / dead:**
- github.com/NSRRC (org, 0 public repos): https://github.com/NSRRC
- light911/NSRRC_TPS05A_BeamMonitor (empty since 2016): https://github.com/light911/NSRRC_TPS05A_BeamMonitor

**Still-open gaps (blocked by tooling, not absence):**
- Chinese-language sources (國家同步輻射研究中心 / 台灣光子源) and Taiwan thesis portals (NDLTD/airiti, NTHU/NCTU): un-probed due to a WebSearch backend outage during round-2; retry when WebSearch is healthy.
