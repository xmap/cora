# SSRL (Stanford Synchrotron Radiation Lightsource) research brief

*Research seed for future CORA deployment pages. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about SSRL, its beamline roster, and its control-software stack so the model work can begin from corroborated facts rather than memory. CORA is not connected to SSRL; the seam section is an initial read, not a commitment. Compiled 2026-06-30 from the SSRL facility pages plus a direct read of the public per-beamline bluesky profiles on GitHub.*

!!! note "Reading posture"
    Public facility pages (`www-ssrl.slac.stanford.edu`) are the source of HARDWARE FACTS (ring, beamline roster, techniques). Public GitHub source (the per-beamline bluesky profiles) is the source of CONTROL-SOFTWARE FACTS (device topology, EPICS PVs, ophyd device classes). Confidence is flagged inline as **[verified]**, **[partly verified]**, or **[unconfirmed]**. Per CORA's deployment-doc lens, the facility software stack is named ONLY at the seam (section 6). Provenance caveat: the per-beamline profiles are published on a SLAC staff member's personal GitHub account (`github.com/tangkong`), not an SSRL org, so treat them as a strong-evidence controls snapshot, the same posture as the ESRF gitlab and NSRRC scattered-repo reads, with every value carried `confirm` until SSRL staff verify it.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | Stanford Synchrotron Radiation Lightsource (SSRL), storage-ring light source | [SSRL](https://www-ssrl.slac.stanford.edu/) |
| Operator | Stanford University for the U.S. DOE Office of Science (at SLAC) | [SSRL](https://www-ssrl.slac.stanford.edu/) |
| Storage ring | SPEAR3 | [SSRL](https://www-ssrl.slac.stanford.edu/) |
| Ring energy | 3.0 GeV (SPEAR3, well established; confirm exact value) | facility/machine docs, **[partly verified]** |
| Beamline count | 25 beam lines, 31 end-stations (8 bending-magnet, 16 insertion-device independently operating) | [SSRL](https://www-ssrl.slac.stanford.edu/) **[verified]** |

SSRL is one of the older US storage-ring light sources (the SPEAR ring, now SPEAR3), co-located at SLAC with LCLS (the XFEL CORA already models as the slac/lcls-mfx deployment). SSRL is the storage-ring source, distinct from LCLS. **[verified]** The most citable hook for CORA's value proposition is the same as the other reverse-engineered fleets: SSRL publishes real per-beamline device topology (EPICS PVs) openly, so the dry-fact seed feeds CORA's intentional model directly, while the governance / provenance / recipe spine that CORA adds is absent from the bluesky profiles.

---

## 2. Candidate beamlines

SSRL publishes per-beamline **bluesky profile collections** (`profile_bluesky/startup/instrument/devices/*.py` + a `happi/db.json` device database) for a subset of its beamlines on the `github.com/tangkong` account. These carry real EPICS PV prefixes and ophyd device classes, so their device topology is directly modellable, the same pattern as the NSLS-II profile collections and Diamond `dodal`. The remaining ~21 SSRL beamlines do not publish a public device manifest (their control config is staff-only); those are out of scope until staff provide facts.

The modellable set (public bluesky profiles, read 2026-06):

| Beamline | Repo | Technique | Detectors (from source) | Control source | Source |
| --- | --- | --- | --- | --- | --- |
| 2-1 | `tangkong/SSRL-2-1` | powder / single-crystal diffraction | Dexela, MarCCD, Pilatus, Xspress3 | public bluesky profile | [SSRL-2-1](https://github.com/tangkong/SSRL-2-1) |
| 2-2 | `tangkong/SSRL-2-2` | continuous XAS / EXAFS (fly-scan) | Xspress3, DXP, FPGA flyers | public bluesky profile | [SSRL-2-2](https://github.com/tangkong/SSRL-2-2) |
| 1-5 | `tangkong/SSRL-1-5` | diffraction / scattering | Dexela, MarCCD, Pilatus, Xspress3 | public bluesky profile | [SSRL-1-5](https://github.com/tangkong/SSRL-1-5) |
| DeNovX | `tangkong/SSRL-DeNovX` | transmission X-ray diffraction | Dexela | public bluesky profile | [SSRL-DeNovX](https://github.com/tangkong/SSRL-DeNovX) |

A fifth repo, `tangkong/SSRL-X-X`, is a beamline-profile **template** (the shared skeleton the four real profiles were cloned from), not a beamline; it is the structural reference, not a modelling target. Technique labels above are inferred from the device set + repo descriptions and need staff confirmation (TECH-1). **[partly verified]**

**Identifier scheme:** SSRL uses `N-M` beamline IDs (sector-station, e.g. 2-1, 2-2, 1-5). EPICS PV roots seen in source are `BL22:...` (beamline 2-2), `BL00:RIO.*` (a shared/utility crate), and per-device IMS motor records (`BL22:IMS:MOTOR1`). This is closer to the NSLS-II / APS EPICS idiom than to Diamond's `dodal` env-resolved prefixes. **[verified]**

---

## 3. Control-system stack, by layer

SSRL is an **EPICS** facility, with the in-scan layer standardized (for the published beamlines) on the **bluesky / ophyd** ecosystem.

### Device IO (the floor)

EPICS Channel Access. The bluesky profiles wrap real EPICS PVs in ophyd device classes: `EpicsMotor` (IMS motor records, e.g. `BL22:IMS:MOTOR1`), `EpicsSignal` over National Instruments RIO crate channels (`BL00:RIO.AI0`, `BL00:RIO.DO00`), and areaDetector-backed detectors (Dexela, MarCCD, Pilatus, Xspress3). This is below CORA's seam; CORA's ControlPort actuates through the EPICS floor exactly as at the 2-BM pilot and the NSLS-II fleet. **[verified]**

### Scan orchestration (the seam layer)

**bluesky** plans + RunEngine, with a per-beamline `instrument` package (the apstools/BITS-style `profile_bluesky/startup/instrument/{devices,plans,callbacks,framework}` layout) and a `happi` device database per beamline. A shared helper library, `tangkong/ssrltools`, carries cross-beamline bluesky tooling. This is the layer CORA's EdgeConductor would conduct over / replace, incrementally and routine-by-routine. **[verified]**

### Fast paths and exceptions

Beamline 2-2 (continuous XAS) carries FPGA-based flyers (`fpga_flyer.py`, `flyer_100e.py`) and a DXP (XIA DXP/Xspress) spectroscopy path for fly-scanning the absorption spectrum, the same fly-scan shape seen at NSLS-II ISS/QAS. The FPGA flyer is the fast trigger/gate surface; confirm whether it is pure EPICS or a direct-socket path (FLY-1). **[partly verified]**

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| `github.com/tangkong` (SLAC staff personal account) | per-beamline bluesky profiles (2-1, 2-2, 1-5, DeNovX) + the SSRL-X-X template + `ssrltools` + `ssrlsim` | [tangkong](https://github.com/tangkong) |
| `github.com/bluesky` | the upstream bluesky / ophyd / areaDetector framework SSRL builds on | [bluesky](https://github.com/bluesky) |
| `github.com/khstone`, `anjanikmaurya`, etc. | scattered per-beamline data-analysis scripts (BL2-1 Pilatus, BL17-2 WAXS) | various |

**Why a per-beamline device model IS buildable from public source (for the four published beamlines).** Each profile's `instrument/devices/*.py` carries real ophyd device classes with literal EPICS PV strings (verified: `BL22:IMS:MOTOR1`, `BL00:RIO.AI0`), and a `happi/db.json` device registry. This is the same dry-fact value as the NSLS-II profile collections. The caveat is provenance (personal account, not an SSRL org) and coverage (only 4 of ~25 beamlines publish a profile); the rest are staff-only.

---

## 5. Data management

Not established from public source in this pass. SSRL's macromolecular-crystallography beamlines historically run the Blu-Ice/DCSS stack and an SSRL sample database (visible in older SLAC projects like `restflow-org/autodrug`), and the bluesky profiles use the standard bluesky document model + suitcase exporters (a `callbacks/live_export.py` is present). The catalog / data-policy / archive chain is an open question for staff (DATA-1). **[unconfirmed]**

---

## 6. The CORA seam (initial read)

First pass, not a committed seam. Applies the 2-BM / FXI lens: device IO is the floor CORA never replaces; the higher scan / orchestration layer is where CORA replaces or drives through; the facility catalog is a source-of-truth contest, not a dependency.

**Where the floor stays the floor (drive through, never CORA).** SSRL device IO is EPICS Channel Access (ophyd-backed). CORA's ControlPort actuates through it exactly as at the APS / NSLS-II EPICS beamlines. Because the floor is EPICS, the APS-pilot ControlPort model carries over with no new control substrate to build.

**What CORA replaces (edge orchestration).** The bluesky RunEngine + per-beamline plans (and the `ssrltools` helpers) are the scan-orchestration layer the 2-BM seam designates as CORA's. CORA's EdgeConductor would conduct routines over the EPICS floor where the bluesky plans sit today. Treat the bluesky profile as DATA to learn from (device topology, axis grouping, the fly-scan structure at 2-2), NOT a spec to mirror. The produced record is identical regardless of the execution layer; pitch CORA on governance, replayability, recipe-binding, never on out-executing bluesky on speed.

**Source-of-truth contest (data).** The `happi` device database and the bluesky document store are the closest analogs to CORA's own model; CORA stays the system of record for the experiment (decisions, recipe ladder, provenance, trust) and treats the bluesky/happi layer as a source to subsume, not a dependency. The MX Blu-Ice/DCSS + sample database (if a MX beamline enters scope) is the same seam tension seen at NSRRC TPS-07A. Decision deferred until a specific SSRL deployment is in scope.

**Coexist.** SLAC facility scheduling / identity (read, do not replace), any SSRL data catalog (an egress / publish target), the LCLS-side infrastructure (separate facility, out of scope).

---

## 7. Open questions (for SSRL staff)

These could not be settled from public sources and need operator confirmation before any seam lock.

1. **Technique confirmation (TECH-1):** confirm the science of 2-1, 2-2, 1-5, DeNovX (inferred from device sets + repo descriptions).
2. **PV namespace:** confirm the per-beamline EPICS prefixes (e.g. is 2-1 `BL21:`?); only 2-2 (`BL22:`) and the shared `BL00:RIO` crate were read verbatim.
3. **Fast-path substrate (FLY-1):** is the 2-2 FPGA flyer pure EPICS or a direct-socket / hardware-trigger path? This bounds the ControlPort surface.
4. **Data catalog (DATA-1):** what is SSRL's data-policy / catalog / archive chain, and does it overlap CORA's system-of-record claim?
5. **Coverage:** do beamlines beyond the four published profiles have a controls manifest CORA could read, or is the rest staff-only?
6. **Provenance:** are the `tangkong` profiles the authoritative beamline config, or a personal snapshot of it?

---

## 8. Source list

**Facility (hardware facts):**
- SSRL: https://www-ssrl.slac.stanford.edu/

**Control system / device topology (public bluesky profiles):**
- SSRL 2-1: https://github.com/tangkong/SSRL-2-1
- SSRL 2-2: https://github.com/tangkong/SSRL-2-2
- SSRL 1-5: https://github.com/tangkong/SSRL-1-5
- SSRL DeNovX: https://github.com/tangkong/SSRL-DeNovX
- SSRL-X-X (template): https://github.com/tangkong/SSRL-X-X
- ssrltools (shared bluesky helpers): https://github.com/tangkong/ssrltools
- bluesky / ophyd framework: https://github.com/bluesky

**Internal-only (named, not reachable):** the SSRL EPICS IOC source and the controls config for the ~21 beamlines without a public bluesky profile.
