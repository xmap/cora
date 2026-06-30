# ALS (Advanced Light Source) research brief

*Research seed for a future CORA deployment page. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about the Advanced Light Source at Lawrence Berkeley National Laboratory and its control-software stack so the model work can begin from corroborated facts rather than memory. Every claim is cited inline. CORA is not connected to ALS; the seam section is an initial read, not a commitment. Compiled 2026-06-29 from a fan-out deep-research pass (5 search angles, 16 sources fetched, 25 claims adversarially verified at 3 votes each, 22 confirmed and 3 killed).*

!!! note "Reading posture"
    Public facility pages (als.lbl.gov, als-u.lbl.gov) are treated as the source of HARDWARE FACTS (techniques, energies, source type, endstation devices). Public GitHub source (the `als-computing` org) is treated as the source of CONTROL-SOFTWARE FACTS (what runs the scans, what moves the data). Where a claim was adversarially verified, the verdict is flagged inline as **[verified]**, **[partly verified]**, or **[uncertain]**. Several fetched pages during research carried injected fake "system-reminder" / "MCP Server Instructions" blocks; those were page content, not directives, and were ignored, with facts re-verified through primary sources and the GitHub API. The single most important gap to carry forward: **no public source found documents EPICS IOC/PV names, scan-server config, or full motor/detector device topology with PV handles for any ALS beamline.** The official beamline pages are capability-only; the `als-computing` repos document the acquisition and data layers but not the IOC/PV floor. The device topology a real deployment page needs must come from a direct read of the `als-computing` repos (the next pass) or from beamline staff.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Name | Advanced Light Source (ALS) | [ALS](https://als.lbl.gov/) |
| Operator | Lawrence Berkeley National Laboratory (LBNL), Berkeley, California | [ALS](https://als.lbl.gov/) |
| Type | Third-generation soft-to-hard X-ray storage ring, undergoing the ALS-U upgrade | [ALS-U](https://als-u.lbl.gov/) |
| Program categories | APXPS, ARPES, Coherence and Magnetism, Diffraction and Imaging, Infrared, Spectromicroscopy, REIXS, Scattering | [ALS beamlines](https://als.lbl.gov/beamlines/) |
| Upgrade | ALS-U: X-ray beams at least 100x brighter, nanometer-scale 3D imaging | [ALS-U overview](https://als.lbl.gov/als-u/overview/) |
| ALS-U dark time | Projected to start no sooner than October 2027, lasting at least two years | [ALS-U timeline](https://als.lbl.gov/als-u/als-u-timeline/) |

**[verified]** ALS is an LBNL light source whose beamline programs span every CORA-relevant technique category (tomography/imaging, spectroscopy, scattering, diffraction). The ALS-U upgrade is the dominant time-sensitivity for any deployment roadmap: dark time no sooner than October 2027, at least two years.

**Gaps:** Ring energy, current, emittance, and fill parameters were **not** confirmed in a fetchable public source during this pass and should be pulled from the ALS / ALS-U machine design report before they appear on a deployment page. **[uncertain]** The "100x brighter" figure is a design-spec / promotional number, not a measured post-commissioning result. **[partly verified]**

---

## 2. Beamline catalog

The beamlines with publicly confirmed technique mappings that fall in CORA's deployment scope. Techniques are from the ALS master beamline directory and per-beamline pages. No beamlines invented; the program list is broader than the rows below (this table is the CORA-relevant subset, not the full ALS port list).

| Beamline | Technique | Source / energy | Status note | Reference |
| --- | --- | --- | --- | --- |
| 8.3.2 | Hard X-ray micro-tomography (micro-CT) | Superbend, 6,000-43,000 eV, ~1 micron | Operating; tomography | [8-3-2](https://als.lbl.gov/beamlines/8-3-2/), [microct.lbl.gov](https://microct.lbl.gov/) |
| 7.0.1.2 (COSMIC Imaging) | STXM, ptychography, tomography | Soft X-ray undulator | Operating; imaging branch | [7-0-1-2](https://als.lbl.gov/beamlines/7-0-1-2/) |
| 7.0.1.1 (COSMIC Scattering) | Coherent scattering, SAXS, XRD, magnetic + resonant scattering | 250-1,600 eV, EPU3.8 undulator, linear/circular polarization | Closes at ALS-U dark time, migrates to planned FLEXON at 10.0.1 | [7-0-1](https://als.lbl.gov/beamlines/7-0-1/) |
| 7.3.3 | SAXS / WAXS / GISAXS | Q ~0.004-3.5 inverse Angstrom | Operating; scattering | [7-3-3](https://als.lbl.gov/beamlines/7-3-3/) |
| 5.3.1 | (finch frontend deployed; technique not confirmed this pass) | - | Bluesky/finch endstation | [als-computing](https://github.com/als-computing) |
| 6.0.1.3 (AMBER) | (finch frontend deployed; technique not confirmed this pass) | - | Bluesky/finch endstation | [als-computing](https://github.com/als-computing) |

**[verified]** 8.3.2 = hard X-ray micro-CT (three independent primary sources: the master list, the 8-3-2 page, and the dedicated microct.lbl.gov subdomain). COSMIC is a two-branch undulator beamline: 7.0.1.2 imaging (STXM/ptychography/tomography) and 7.0.1.1 scattering (coherent scattering/SAXS/XRD/magnetic/resonant), with the scattering branch explicitly **not** a microscopy facility. 7.3.3 = SAXS/WAXS/GISAXS.

**COSMIC Scattering device topology [verified]** is the most concrete public device inventory found among ALS beamline pages: a flange-mounted ANDOR iKon-L 936 CCD; a Princeton Instruments MTE3 CCD plus a Si photodiode on a two-theta arm (scannable -10 to 150 degrees, 50 mm perpendicular translation); a vector plane magnet (x-z, 0.1 T uncooled / 0.65 T LN2-cooled). It still lacks EPICS PV names, but it is the cleanest starting device list on the facility side.

**Status caveat [uncertain]:** the `6.0.1.3` number for AMBER is inferred from the `bl6013-finch` repo slug, not stated on a facility page. The `5.3.1` and AMBER technique mappings were not confirmed this pass and should be pulled from their beamline pages before modelling.

---

## 3. Control-system stack, by layer

!!! warning "Corrected by the 8.3.2 repo dive (2026-06-29)"
    The deep-research pass inferred an **EPICS** floor (below). A hands-on read of the `als-computing` org corrected this: **ALS runs BCS (the Beamline Control System), a LabVIEW stack, NOT EPICS.** Confirmed by [`als-computing/als.bcs`](https://github.com/als-computing/als.bcs) ("metadata from text data files created by the Beamline Controls System (BCS)") and [`als-computing/bcs-api`](https://github.com/als-computing/bcs-api) ("Combining LabView BCS with Bluesky": BCS scans wrapped as bluesky ophyd `fly` devices). There are **no EPICS PVs** for 8.3.2. The "central gap" the pass flagged (no public device topology) was also resolved: the device structure is recoverable from the **DXchange / DXfile HDF5 data-record schema** the ALS tooling reads (the SciCat ingester `als-computing/scicat_beamline` and the reconstruction backend `als-computing/microct`); only the live BCS channel handles remain staff-only. See docs/deployments/8-3-2/ and its descriptor deployments/8-3-2/beamline.yaml for the recovered topology. The EPICS-floor bullets below are kept as the original (now-superseded) pass for provenance.

ALS, through its `als-computing` group, standardizes on the **Bluesky data-acquisition ecosystem** for in-scan acquisition and on **Prefect + Globus** for data movement and compute orchestration. This is a materially different posture from NSRRC (heterogeneous per-beamline) and closer to the Diamond `dodal` / Sirius `sophys` facility-framework pattern, though the public evidence is concentrated in a handful of beamlines. The device floor below it is BCS (LabVIEW), with the bluesky layer reaching it through the BCS API rather than over EPICS Channel Access.

### Device IO (the floor): BCS, not EPICS

- **[verified, repo dive]** The floor is **BCS (Beamline Control System), a LabVIEW house-style**, surfaced as scan files (Time Scan, Single Motor Scan, Trajectory Scan) whose headers carry the DXchange / DXfile HDF5 device-state data record ([`als-computing/als.bcs`](https://github.com/als-computing/als.bcs)). No public per-beamline BCS channel manifest exists; the live handles are staff-only (CTRL-1).
- **[superseded inference]** The deep-research pass guessed an EPICS device floor (consistent with a generic Bluesky/Ophyd layer). This is wrong for ALS: BCS is LabVIEW, and bluesky reaches it through the BCS API, not EPICS CA. Kept for provenance.
- A claim asserting Ophyd's EPICS/pva/serial protocol detail was **refuted** in verification (1-2) and must not be carried forward. **[refuted]**

### Orchestration + scan engine (the seam layer)

- **In-scan acquisition: Bluesky ecosystem.** The `als-computing` org hosts `bl531-finch` ("The Finch frontend used at the ALS Beamline 5.3.1") and `bl6013-finch` ("The finch frontend for AMBER"), both forks of `bluesky/finch`, requiring **Bluesky Queue Server, Tiled, and Ophyd-Websocket**. Org-wide Bluesky adoption is corroborated by `tiled`, `bluesky-web`, `beamline531`, and `dichroview`. **[verified]** ([als-computing](https://github.com/als-computing))
- **Data movement + compute: Prefect + Globus (`splash_flows`).** `als-computing/splash_flows` provides "Prefect workflows to move data and run computing tasks," using "Globus for data movement between local servers and back and forth to NERSC." `orchestration/flows/` contains `bl7012`, `bl832`, `bl733`, and `scicat` flows. **[verified]** ([splash_flows](https://github.com/als-computing/splash_flows))
- **Reconstruction targets.** `alcf.py` = "Run tomography reconstruction Globus Compute Flows at ALCF" (Deployed); `nersc.py` = "Run tomography reconstruction using SFAPI at NERSC" (WIP). Per-beamline wiring is loosely uniform (bl7012 uses a shell script, bl832 uses a `prefect.yaml`), so treat "deployment scripts per beamline" as a loose description, not a uniform contract. **[partly verified]** (the single dissenting vote flagged the wording, not the substance)

### GUI

- The `finch` frontends are React component libraries for Bluesky beamlines (Queue Server + Tiled + Ophyd-Websocket). `bluesky-web` and `dichroview` are additional web tooling. **[verified]** ([als-computing](https://github.com/als-computing))

### Data acquisition + formats

- **Tiled** is present in the stack as the structured-data access layer fronting Bluesky documents. A stronger claim (Tiled integrated into tomography reconstruction visualization with remote slicing / live streaming) was **refuted** in verification (1-2) and must not be carried forward. **[refuted]**
- `als-computing/microct` provides "Jupyter notebooks to reconstruct and visualize microCT data from ALS beamline 8.3.2." A direct file-tree inspection plus a grep for `epics|caget|caput|pvaccess|IOC|motor|detector|aerotech|pso` returned **zero** controls matches: the only motor/detector hits are HDF5 metadata reads from already-acquired files. This repo is the **compute/recon layer**, not the controls stack. **[verified]** ([microct](https://github.com/als-computing/microct))

### 8.3.2 device topology, from the DXchange / DXfile HDF5 data record

**[verified, repo dive]** against `als-computing/scicat_beamline` (`src/scicat_beamline/ingesters/als_832_dx_4.py`) and `als-computing/microct` (`backend/ALS_recon_functions.py`). The HDF5 metadata tree names the device hierarchy and its axes; this is the device STRUCTURE that seeded `deployments/8-3-2/beamline.yaml`. The live BCS handles are NOT public (CTRL-1).

| HDF5 path | CORA device | Family |
| --- | --- | --- |
| `/measurement/instrument/source/{source_name,current,beam_intensity_incident}` | Superbend + StorageRing | InsertionDevice (Supply) + StorageRing (loose) |
| `/measurement/instrument/monochromator/{energy,setup/Z2,setup/turret1,setup/turret2,setup/temperature_tc2,setup/temperature_tc3}` | Monochromator | Monochromator |
| `/measurement/instrument/slits/setup/{hslits_A_Door,hslits_A_Wall,hslits_center,hslits_size,vslits_Lead_Flag}` | BeamSlit | Slit |
| `/measurement/instrument/attenuator/setup/filter_y` | BeamFilter | Filter |
| `/measurement/instrument/sample_motor_stack/setup/{axis1pos,axis2pos,axis5pos,sample_x,sample_y}` | SampleRotary + SamplePositioning | RotaryStage + LinearStage |
| `/measurement/instrument/detection_system/scintillator/scintillator_type` | Scintillator | Scintillator |
| `/measurement/instrument/detection_system/objective/camera_objective` | CameraObjective | Objective |
| `/measurement/instrument/detector/{model,pixel_size,binning_x,binning_y,exposure_time,temperature,dimension_x,dimension_y,dark_field_value,delay_time}` | Camera | Camera |
| `/measurement/instrument/camera_motor_stack/setup/{camera_distance,camera_elevation,tilt_motor}` | DetectorStack | LinearStage |

Open: which `axisNpos` is the tomographic rotation (ROT-1); detector specs are per-dataset, not a fixed manifest (DET-1); BCS live handles not public (CTRL-1).

---

## 4. Where the code lives

The **`github.com/als-computing` org** is the single most valuable controls/orchestration source and the primary modelling input. Repo facts below from the deep-research pass (2026-06-29); a direct API-level read is the next pass.

| Repo | Role | Notes |
| --- | --- | --- |
| [als-computing/splash_flows](https://github.com/als-computing/splash_flows) | **Primary orchestration target.** Prefect + Globus data movement and compute; flows for bl7012, bl832 (8.3.2 tomo), bl733, scicat; reconstruction at ALCF (deployed) + NERSC (WIP) | The clearest cross-beamline orchestration evidence |
| [als-computing/microct](https://github.com/als-computing/microct) | 8.3.2 microCT reconstruction + visualization (Jupyter) | Compute/recon only; **no controls / IOC / PV / motor topology** |
| als-computing/bl531-finch | Beamline 5.3.1 finch frontend (fork of bluesky/finch) | Bluesky Queue Server + Tiled + Ophyd-Websocket |
| als-computing/bl6013-finch | AMBER (6.0.1.3) finch frontend (fork of bluesky/finch) | Same Bluesky stack |
| als-computing/ArroyoXPS | Real-time APXPS data analysis; **explicitly targets integration with the beamline control system** for the new Real-Time Ambient-Pressure XPS instrument | The rare repo with explicit controls relevance |
| als-computing/tiled, bluesky-web, dichroview, beamline531 | Bluesky-ecosystem web/stream tooling | Corroborate org-wide Bluesky adoption |
| als-computing/view_tomography_recon_app | 3D tomography reconstruction viewer (TypeScript) | Post-acquisition visualization |

**Non-GitHub hosts: not probed this pass.** Whether ALS keeps a beamline-internal GitLab carrying the IOC/PV-level topology (the gap above) is an open question. **[uncertain]**

---

## 5. Data management + processing

- **Acquisition documents** flow through the Bluesky stack with **Tiled** as the structured-access layer. **[verified]**
- **Tomography reconstruction** (8.3.2 / bl832 and bl7012) runs off-facility: **Globus Compute Flows at ALCF** (deployed) and **SFAPI at NERSC** (in development), orchestrated by `splash_flows`. **[verified]**
- `als-computing/microct` is the reconstruction + visualization toolkit for 8.3.2 microCT data; `view_tomography_recon_app` is a 3D recon viewer. **[verified]**
- No facility-wide data-of-record / metadata catalog was characterized this pass beyond the `scicat` flow in `splash_flows` (suggesting a SciCat integration). **[uncertain]**

---

## 6. The CORA seam (initial read)

This is a first pass, not a committed seam. It applies the same 2-BM / FXI / NSRRC lens: device IO is the floor CORA never replaces; the higher scan/orchestration layer is where CORA replaces or drives through.

**Where BCS stays the floor.** ALS beamline device IO is **BCS (LabVIEW)**, reached by the bluesky layer through the BCS API. CORA's ControlPort would actuate **through** this floor exactly as at 2-BM and FXI; CORA never owns the BCS channels or the device layer. The live BCS handles are not public (staff-only, CTRL-1), so they are carried pending, the way the MX3 / ID32 heterogeneous-control precedents model opaque edge handles. **[verified, repo dive]**

**What CORA would replace or drive through.** ALS is closer to the facility-framework pattern (Bluesky everywhere) than to NSRRC's heterogeneous per-beamline orchestration. The seam is therefore likely uniform across beamlines:

1. **In-scan acquisition (Bluesky Queue Server + Ophyd).** CORA's EdgeConductor would replace or drive the Bluesky plan/queue orchestration over the Ophyd floor, the FXI / NSLS-II pattern, not the 2-BM TomoScan-replacement pattern. The finch frontends are the human GUI CORA's spine would sit behind or beside.
2. **Data movement + compute (`splash_flows`, Prefect + Globus).** This is a post-acquisition orchestration layer moving data to ALCF/NERSC for reconstruction. CORA's data-of-record (PG event store) and its own compute conduct path would **subsume** the Prefect/Globus orchestration as a source-to-learn-from, not a system CORA depends on. The detector-native HDF5 files become a source to subsume, not a dependency.

**Open design questions.**
- The 8.3.2 device structure is recovered from the DXfile HDF5 data record, but the live BCS channel handles per device are staff-only. Where (if anywhere) is the BCS channel manifest version-controlled? **This is the top blocker before CORA can actuate 8.3.2.**
- What is the full beamline-to-stack mapping beyond the handful covered (8.3.2, 7012, 733, 5.3.1, AMBER)? Which other ALS beamlines run Bluesky vs. legacy SPEC/EPICS-only stacks?
- PSS / interlock implementation: no public source exposes this; must come from staff.
- Which beamlines survive ALS-U unchanged vs. are rebuilt/relocated, so deployment effort targets stable instruments (e.g. is 8.3.2 micro-CT affected by dark time)?
- Confirmed name, location (10.0.1?), and scope of the planned FLEXON beamline that inherits COSMIC Scattering post-ALS-U.

---

## 7. Confidence + gaps

**Well-corroborated (multiple primary sources or verified):**
- Facility identity and program span (8 program categories covering all CORA-relevant techniques). **[verified]**
- 8.3.2 = hard X-ray micro-CT, Superbend, 6-43 keV, ~1 micron (three independent sources). **[verified]**
- COSMIC two-branch architecture: 7.0.1.2 imaging vs 7.0.1.1 scattering. **[verified]**
- COSMIC Scattering endstation device inventory (ANDOR iKon-L 936, Princeton MTE3 + Si photodiode on two-theta arm, vector plane magnet). **[verified]**
- 7.3.3 = SAXS/WAXS/GISAXS. **[verified]**
- ALS standardizes on Bluesky (finch at 5.3.1 and AMBER; Tiled; Ophyd-Websocket; Queue Server). **[verified]**
- Prefect + Globus orchestration (`splash_flows`) for bl832/8.3.2, bl7012, bl733; reconstruction at ALCF (deployed) / NERSC (WIP). **[verified]**
- ALS-U dark time no sooner than Oct 2027, at least two years. **[verified]**

**Uncertain or single-source:**
- Ring machine parameters (energy/current/emittance/fill). **[uncertain]**
- EPICS IOC/PV floor and per-beamline device topology with PV handles: **no public source.** **[uncertain]** This is the central gap.
- COSMIC Scattering closes at dark time and migrates to a planned FLEXON beamline at 10.0.1 (single source; "planned" / "will close"; name and location may change). **[partly verified, medium confidence]**
- AMBER = 6.0.1.3 (inferred from repo slug). **[uncertain]**
- SciCat as the facility metadata catalog (inferred from a `scicat` flow). **[uncertain]**

**Refuted in verification (do NOT carry forward):**
- Ophyd EPICS/pva/serial protocol detail with metadata propagation (1-2).
- COSMIC ptychography sub-10 nm resolution for 2D/3D (0-3).
- Tiled integrated into tomography reconstruction visualization with remote slicing / live streaming (1-2).

**What to ask facility staff:**
1. ALS / ALS-U ring machine parameters.
2. The EPICS IOC/PV namespace and device tree for the modelling target (8.3.2), and where it is version-controlled.
3. The Bluesky plan / queue-server configuration for 8.3.2 acquisition (the scan orchestration CORA's edge would replace or drive).
4. The 8.3.2 detector + motion inventory (camera model, rotation stage / Aerotech + PSO if any, sample positioning), with PV handles.
5. PSS / interlock implementation at the endstation.
6. ALS-U impact on 8.3.2 specifically: does it go dark, get rebuilt, or relocate.
7. User-office / proposal system and role/permission model, for the governance seam.

---

## 8. Recommended deployment beamline

**Recommendation: ALS 8.3.2 (Hard X-ray Micro-Tomography) as the first ALS deployment.**

**Why 8.3.2:**

- **It reuses CORA's strongest existing vocabulary.** CORA has already modelled hard X-ray micro-CT at APS 2-BM (the operational pilot), MAX IV TomoWise, PSI I-TOMCAT, ALBA FAXTOR, Sirius MOGNO, and NSLS-II FXI. 8.3.2 is a **reuse-and-reinforce** tomography deployment on a new Site, not a from-scratch one.
- **It is the best-documented ALS beamline across all three layers found.** Technique and source are confirmed by three independent primary sources; the acquisition layer is Bluesky; the compute/recon layer has a dedicated public repo (`microct`) and an orchestration flow (`splash_flows/bl832`) with a real reconstruction target (ALCF, deployed). No other ALS beamline has this depth of public evidence.
- **The orchestration seam is the FXI / NSLS-II Bluesky pattern, already in CORA's repertoire.** Unlike the 2-BM TomoScan-replacement seam, ALS runs Bluesky natively, so the seam transfers from the FXI exercise rather than the 2-BM one. This tests the Bluesky-edge seam at a new Site.
- **One Site kernel port enables follow-on coverage.** Modelling the ALS Site / Federation envelope once sets up cheap follow-on pages for the COSMIC branches (7.0.1.1/.2) and 7.3.3, which share the org's Bluesky + splash_flows stack.

**Why not COSMIC first:** despite COSMIC Scattering having the cleanest public *device* inventory, it (a) closes at ALS-U dark time and migrates to a provisional FLEXON beamline, making it a moving target, and (b) is soft X-ray scattering, a less-reused CORA vocabulary than tomography. It is a strong **second** deployment (and the best device-topology reference), not the first.

**Caveats carried into modelling:**
- **The controls floor is unconfirmed.** No public source exposed 8.3.2's EPICS IOC/PV or full motor/detector topology this pass. The next step is a direct read of the `als-computing` repos (`microct`, `splash_flows/orchestration/flows/bl832`, and any 832 ophyd/BITS tree) to recover the device layer; what the repos do not yield must come from staff. Until then, every physical/control fact stays `confirm`-pending, exactly as the other reverse-engineered pages are framed.
- `als-computing/microct` is reconstruction-only and will **not** yield device topology; do not mistake its HDF5 metadata reads for a controls model.
- ALS-U scheduling (dark time no sooner than Oct 2027) is a roadmap constraint: confirm 8.3.2's upgrade fate before committing modelling effort.

---

## 9. Source list

**Facility (hardware facts):**
- ALS: https://als.lbl.gov/
- ALS beamlines directory: https://als.lbl.gov/beamlines/
- Beamline 8.3.2: https://als.lbl.gov/beamlines/8-3-2/
- Beamline 8.3.2 (micro-CT group site): https://microct.lbl.gov/
- COSMIC (7.0.1) Scattering branch: https://als.lbl.gov/beamlines/7-0-1/
- COSMIC Imaging (7.0.1.2): https://als.lbl.gov/beamlines/7-0-1-2/
- Beamline 7.3.3 (SAXS/WAXS/GISAXS): https://als.lbl.gov/beamlines/7-3-3/

**ALS-U (upgrade context):**
- ALS-U: https://als-u.lbl.gov/
- ALS-U overview: https://als.lbl.gov/als-u/overview/
- ALS-U timeline: https://als.lbl.gov/als-u/als-u-timeline/

**Control software (GitHub):**
- als-computing org: https://github.com/als-computing
- als-computing/splash_flows: https://github.com/als-computing/splash_flows
- als-computing/microct: https://github.com/als-computing/microct

**Papers:**
- COSMIC beamline (J. Phys. Conf. Ser. 425 192011): https://iopscience.iop.org/article/10.1088/1742-6596/425/19/192011/meta

**Still-open gaps (require the repo dive or staff):**
- ALS EPICS IOC/PV namespace and 8.3.2 device topology with PV handles: no public source this pass; read the `als-computing` repos next, then ask staff.
- ALS / ALS-U ring machine parameters.
- Beamline-internal GitLab (if any) carrying the controls floor: not probed.
- 5.3.1 and AMBER (6.0.1.3?) technique mappings.
- FLEXON beamline (10.0.1?) confirmed name/location/scope.
