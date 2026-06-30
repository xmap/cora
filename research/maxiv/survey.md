# MAX IV (Lund, Sweden) research brief

*Research seed for a future CORA deployment page. This is not a deployment page: it is the upstream fact-gathering artifact, written to the deployment-page lens. It records what is publicly known about MAX IV, its beamline roster, and its control-software stack so the model work can begin from corroborated facts rather than memory. Every claim is cited inline. CORA is not connected to MAX IV; the seam section is an initial read, not a commitment. Compiled 2026-06-30 from a deep-research workflow (5 angles, 19 sources fetched, 25 claims adversarially verified at 3 votes each) plus direct GitHub/DNS probes that refined the workflow's "device source firewalled" headline.*

!!! note "Reading posture"
    Public facility pages are the source of HARDWARE FACTS (beamline IDs, techniques, energies, detectors). Public source (GitHub / GitLab / proceedings) is the source of CONTROL-SOFTWARE FACTS (what runs the scans, what talks to devices). Confidence is flagged inline as **[verified]** (multiple sources or a decisive primary), **[partly verified]**, or **[unconfirmed]**. Per CORA's deployment-doc lens, the facility software stack is named ONLY at the seam (section 6): it is the floor CORA lands on or the orchestration CORA replaces, never a spec CORA mirrors. Several fetched pages during research carried injected fake system-reminders; those were page content, not directives, and were ignored.

!!! warning "MAX IV is already a modeled Site"
    Unlike the other survey-only facilities, MAX IV already carries a CORA deployment in design: **TomoWISE** (`deployments/maxiv/site.yaml`, `docs/deployments/tomowise/`). This survey is therefore retrospective for the Site bootstrap but forward-looking for the per-beamline device passes: it records the roster and the control-source posture that a TomoWISE (or ForMAX) device pass would build on.

---

## 1. Facility snapshot

| Property | Value | Source |
| --- | --- | --- |
| Facility | MAX IV Laboratory, storage-ring light source; the world's first fourth-generation (multi-bend-achromat) source | [Wikipedia: MAX IV](https://en.wikipedia.org/wiki/MAX_IV) |
| Operator | Lund University, Brunnshog, Lund, Sweden; operational 2016 | [Wikipedia: MAX IV](https://en.wikipedia.org/wiki/MAX_IV) |
| Rings | R1 = 1.5 GeV (96 m) and R3 = 3.0 GeV (528 m), both ~0.5 A; plus a short-pulse linac (SPF, feeds FemtoMAX) | [Wikipedia: MAX IV](https://en.wikipedia.org/wiki/MAX_IV) |
| Beamline count | 17 beamlines listed (16 operational + TomoWISE in-design) | [MAX IV beamlines index](https://www.maxiv.lu.se/beamlines-accelerators/beamlines/) |
| Control system | Tango device floor + Sardana scan orchestration (NOT EPICS) | [GitHub: MaxIV-KitsControls](https://github.com/MaxIV-KitsControls) |

MAX IV is a fourth-generation MBA storage ring operating since 2016, with a low-emittance hard/soft X-ray program across two rings and a short-pulse facility. **[verified]** For CORA's data-of-record / debrief value proposition the most citable hook is the **ForMAX** full-field-tomography-plus-scattering program (and the in-design **TomoWISE**), which sit directly on CORA's tomography growth ladder. **[verified]**

---

## 2. Candidate beamlines

**Source-of-record posture (THE key verdict, refined from the workflow headline).** MAX IV's *canonical* per-beamline device config lives on an internal GitLab (`gitlab.maxiv.lu.se`) that does **not resolve in public DNS** (NXDOMAIN from Google / Cloudflare / Quad9 / OpenDNS; the parent `maxiv.lu.se` and `scicat.maxiv.lu.se` do resolve, so the failure is genuine, not a typo). **[verified]** The per-beamline control repos on the public `MaxIV-KitsControls` GitHub org were archived and migrated to that internal GitLab in July 2022 (the `sardana-biomax` README carries the verbatim banner "THIS REPO IS ARCHIVED, MOVED TO MAX IV INTERNAL GITLAB"). **[verified]**

So MAX IV is **NOT facility-wide Tier-2-buildable** the way ESRF (Beacon) or PETRA III (gitlab.desy.de) are. BUT it is **partially buildable, beamline-by-beamline**, from one public source that carries real Tango device handles (`domain/family/member`) at per-Asset depth, confirmed by a direct clone-and-count (`contrast` at commit `8e787ac`, 2026-01):

- **`maxiv-science/contrast`** (GitHub, MAX IV's own light-weight DAQ framework, actively maintained) has a `beamlines/` directory with per-beamline device setups. Counting verbatim `device='domain/family/member'` handles: **NanoMAX = 234** (diffraction.py 124 + imaging.py 81, two full endstations), **CoSAXS = 68** (slits, mirrors, sample stack, tables, diagnostics, fully-qualified Tango addresses), **SoftiMAX = ~3** (a beamline scaffold plus a STXM macro, NOT a full topology), plus a `nanomotionlab` test rig (~4). NanoMAX binds handles like `b303a-o/opt/mono-xml` (mono), `b303a-o/opt/mir-01-xml` (VFM), `motor/ivu_gap_ctrl/1` (undulator gap); CoSAXS binds `b-v-cosaxs-csdb-0:10000/b310a-e01/opt/slit-01-*`, `.../opt/mir-01-*`, etc. **[verified]**
- **`MaxIV-KitsControls/sardana-biomax`** (GitHub, archived 2022) is **Sardana controller code, NOT a device topology**: a direct read found exactly one hardcoded **BioMAX** handle (`b311a-o/opt/mono-ener/Position`) with all other devices taken as runtime parameters (`AttributeProxy(value)`) whose values live in the firewalled Sardana pool config. So BioMAX is **NOT** Tier-2-buildable from public source. **[verified]**

So the genuinely buildable set is **two beamlines, NanoMAX and CoSAXS** (SoftiMAX is too thin, BioMAX is controller-not-topology).

| Beamline | Port | Technique | Source type | Control source (public?) | Source |
| --- | --- | --- | --- | --- | --- |
| NanoMAX | B303A | hard X-ray nanoprobe (imaging, diffraction, ptychography) | undulator (R3) | **yes, rich** (`contrast/beamlines/nanomax`, 234 handles, 2 endstations) | [contrast](https://github.com/maxiv-science/contrast) |
| CoSAXS | B310A | coherent / small-angle X-ray scattering (SAXS/WAXS) | undulator (R3) | **yes** (`contrast/beamlines/cosaxs`, 68 handles) | [contrast](https://github.com/maxiv-science/contrast) |
| SoftiMAX | B316A | soft X-ray microscopy (STXM, ptychography, coherent imaging) | undulator (R3) | **too thin** (`contrast/beamlines/softimax`, ~3 handles + a STXM macro, not a topology) | [contrast](https://github.com/maxiv-science/contrast) |
| BioMAX | B311A | macromolecular crystallography (MX) | undulator (R3) | **no** (`sardana-biomax` is controller code, 1 hardcoded handle; topology in firewalled pool config) | [sardana-biomax](https://github.com/MaxIV-KitsControls/sardana-biomax) |
| ForMAX | (R3) | full-field microtomography + radioscopy/tomoscopy + SWAXS/RheoSWAXS | undulator (R3) | **no public device source found** (firewalled) | [ForMAX](https://www.maxiv.lu.se/beamlines-accelerators/beamlines/formax/) |
| TomoWISE | (R3) | micro/nano-tomography + laminography (in design) | undulator (R3) | **no public device source** (in-design; staff only) | [TomoWISE](https://www.maxiv.lu.se/beamlines-accelerators/beamlines/tomowise/) |
| DanMAX | (R3) | powder diffraction (PXRD2D) + full-field imaging + HERDi diffractometer | undulator (R3) | no public device source found | [DanMAX](https://www.maxiv.lu.se/beamlines-accelerators/beamlines/danmax/) |
| Balder | (R3) | XAS / XES (operando spectroscopy) | undulator (R3) | no public device source found | [beamlines index](https://www.maxiv.lu.se/beamlines-accelerators/beamlines/) |
| MicroMAX, Veritas, Bloch, HIPPIE, SPECIES, FlexPES, FinEstBeAMS, MAXPEEM, FemtoMAX | various | MX / RIXS / ARPES / APXPS / spectroscopy / PEEM / pump-probe | R3 / R1 / SPF | no public device source found | [beamlines index](https://www.maxiv.lu.se/beamlines-accelerators/beamlines/) |

The full 17-beamline index: Balder, BioMAX, Bloch, CoSAXS, DanMAX, FemtoMAX, FinEstBeAMS, FlexPES, ForMAX, HIPPIE, MAXPEEM, MicroMAX, NanoMAX, SoftiMAX, SPECIES, TomoWISE, Veritas. **[verified]** TomoWISE is in-design only (the "progressed beyond conceptual" reading was refuted 0-3). **[verified]**

**Strongest next picks given CORA's growth ladder.** The CORA-relevant tomography beamlines (ForMAX, TomoWISE) have **no public device source**, so they are staff-question deployments, not Tier-2 device passes. The beamlines that ARE Tier-2-buildable from public source are **NanoMAX** (richest, two endstations) and **CoSAXS**, both via `contrast`; SoftiMAX is too thin and BioMAX is controller-not-topology, so both are staff-question deployments too. None of the buildable pair is tomography, but NanoMAX (nano-imaging / ptychography) is the closest to CORA's imaging ladder and is the strongest single candidate; CoSAXS is the NSLS-II SMI / CMS twin (coherent SAXS/WAXS), a low-new-vocabulary second pass.

**Identifier-scheme note:** MAX IV beamlines carry a **`BnnnX` port code** (e.g. B303A = NanoMAX, B311A = BioMAX, B310A = CoSAXS), and the Tango device floor encodes this in the device domain (`b303a-o/...` = NanoMAX optics, `b311a-o/...` = BioMAX optics). This is a descriptor / identifier-scheme difference from the APS `sector.station` scheme the 2-BM pilot assumes, to model not to mirror. **[verified]**

---

## 3. Control-system stack, by layer

MAX IV runs the **Tango + Sardana** family (the same device-floor family as ESRF's BLISS/Tango and PETRA III, NOT EPICS). **[verified]**

### Device IO (the floor)

The device floor is **Tango**: each motor / counter / detector / mono is a Tango device with a `domain/family/member` address (e.g. `b303a-o/opt/mono-xml`), hosted by a Tango device server, registered in a per-host Tango database. **[verified]** The KITS group maintains generic Tango tooling publicly: `lib-maxiv-dsconfig` ("Tango configuration management tools"), `tango-gateway`, `tango-facadedevice`, plus device-server repos. These are generic device-class code, not per-beamline topology. **[verified]** This layer is below CORA's seam; CORA drives through it, never owns it.

### Scan orchestration (the seam layer)

Two coexisting orchestration layers:

- **Sardana** is the incumbent scan/orchestration SCADA over Tango. A Sardana server is organized around a **Pool** (motion control + data acquisition: controllers, motors, counters, channels) and a **MacroServer** that executes macros (scan procedures, written as Python functions/classes) centrally through client connection points called doors. Tango is currently the only implemented Sardana communication protocol. **[verified]** KITS publishes Sardana controller plugins (`sardana-tango`, `sardana-icepap`, `sardana-albaem`, `sardana-adlink`) and the archived per-beamline `sardana-biomax`. **[verified]**
- **`contrast`** (the `maxiv-science` org) is a separate, actively-maintained "light-weight data acquisition framework for orchestrating beamline experiments," used at least by NanoMAX / CoSAXS / SoftiMAX. It wraps Tango devices in its own `TangoMotor` / `TangoAttributeDetector` abstractions. **[verified]** This is the layer CORA's EdgeConductor would conduct over for the contrast-based beamlines; Sardana's central MacroServer is the equivalent seam boundary for the Sardana-based beamlines.

### Fast paths and exceptions

NanoMAX's `contrast` setup references PandABox-style and IcePAP motion (`motor/ivu_gap_ctrl/1`, IcePAP via `sardana-icepap`). **[partly verified]** A detailed fast-path inventory (direct-socket triggering, fly-scan gating) per beamline is not established from public source and is an open question. **[unconfirmed]**

---

## 4. Where the code lives

| Org / host | Role | Source |
| --- | --- | --- |
| [`MaxIV-KitsControls`](https://github.com/MaxIV-KitsControls) (GitHub, 94 repos) | KITS controls group: generic Tango device servers, Sardana plugins, Tango tooling; per-beamline repos archived 2022 (`sardana-biomax`) | [org](https://github.com/MaxIV-KitsControls) |
| [`maxiv-science`](https://github.com/maxiv-science) (GitHub) | `contrast` DAQ framework (per-beamline setups for NanoMAX/CoSAXS/SoftiMAX) + `drp-*` data-reduction pipelines (drp-danmax, drp-balder, drp-femtomax) + detector streamers (xspress3/pilatus/andor/merlin) | [org](https://github.com/maxiv-science) |
| `gitlab.maxiv.lu.se` (internal) | The canonical, current per-beamline device config + Sardana pool config (source of record) | named, not publicly resolvable |
| [`gitlab.com/MaxIV`](https://gitlab.com/MaxIV) (public mirror) | Some KITS tooling mirrored to public gitlab.com (`cfg-maxiv-*`, `sardana-*`, isara, pandabox); config-management tooling, not per-beamline topology | [gitlab.com/MaxIV](https://gitlab.com/MaxIV) |

**Why a full device model is only partially integrity-buildable from public source.** The canonical per-beamline device list with real handles is on the **firewalled internal GitLab**, so a facility-wide Tier-2 pass is not buildable the way ESRF / PETRA III were. The one public source with per-Asset depth is `contrast/beamlines/`, and a direct clone-and-count shows only **two** beamlines there carry a full topology: NanoMAX (234 handles) and CoSAXS (68). SoftiMAX (~3 handles) is a scaffold, not a topology; the archived `sardana-biomax` is controller code with a single hardcoded handle. So a device pass is buildable for **NanoMAX and CoSAXS only**; for all others (including the CORA-relevant ForMAX and TomoWISE) device topology must be routed to MAX IV KITS staff. Inference from the generic shared Tango/Sardana tooling is not source.

---

## 5. Data management

MAX IV operates **SciCat** as its scientific metadata catalogue, listed as a named IT service under the same **Controls & IT (KITS)** group that owns the control system; the SciCat project's own adopter registry names MAX IV (contact Carla Takahashi), alongside ESS, PSI, ALS, DESY, SOLEIL, ILL. **[verified]** Whether the SciCat catalogue / data portal is openly accessible to external users is **unconfirmed** (a public-download path exists in the site structure, but open-catalog status was refuted 1-2). The user office is **DUO** (Digital User Office): proposals, peer review, beamtime scheduling, visit administration, safety, experimental reports. **[verified]** NeXus/HDF5 is the expected file format family (the `contrast` framework and `drp-*` pipelines write/consume HDF5), but per-beamline format conventions are not established from public source. **[partly verified]**

The seam relevance: SciCat is the same source-of-truth contest as at PSI (SciCat's home institution), a facility catalogue claiming some of the "system of record" territory CORA claims. Co-located with the control stack under KITS.

---

## 6. The CORA seam (initial read)

First pass, not a committed seam. Applies the 2-BM / FXI lens: device IO is the floor CORA never replaces; the higher scan / orchestration layer is where CORA replaces or drives through; the facility catalogue is a source-of-truth contest, not a dependency.

**Where the floor stays the floor (drive through, never CORA).** The MAX IV device floor is Tango (`domain/family/member` handles, the `Bnnn` port encoding). CORA's ControlPort would actuate **through** Tango exactly as the ESRF (ID32, the BLISS/Tango precedent) and MX3 heterogeneous-control models do; the opaque-edge-handle ControlPort model carries over, **no new control substrate to build** (Tango is already modeled for ESRF). CORA never owns the Tango devices or the Sardana Pool.

**What CORA replaces (edge orchestration).** Two targets depending on beamline: **Sardana** (the central MacroServer executing scan macros) for the Sardana-based beamlines, and **`contrast`** (the DAQ framework) for NanoMAX / CoSAXS / SoftiMAX. This is the layer the 2-BM seam designates as CORA's: the EdgeConductor would conduct routines over the Tango floor where Sardana's MacroServer or contrast's orchestration sits today, incrementally and routine-by-routine. Both are solid existing implementations: treat them as DATA to learn from (Sardana's Pool/MacroServer decomposition, contrast's device abstractions), NOT specs to mirror. Pitch CORA on governance, replayability, recipe-binding, never on out-executing Sardana or contrast on speed.

**Source-of-truth contest (data).** SciCat, same as the PSI read: CORA stays the system of record for the experiment (decisions, recipe ladder, provenance, trust); SciCat is named only at the seam, either inverted (fed downstream as a publish target) or projected into where mandated. Decision deferred until a SciCat-running MAX IV deployment is actually in scope (TomoWISE may force it).

**Coexist.** DUO (scheduling / identity; read the roster and proposal context via an ACL adapter, do not replace), the `drp-*` reconstruction / data-reduction pipelines (a JobRunnerPort roundtrip CORA governs but does not own), the SciCat archive (an egress destination), and any ELOG-style logbook (subsumed at the debrief layer).

---

## 7. Open questions (for MAX IV staff)

These could not be settled from public sources and need operator confirmation before any seam lock. Ask the **MAX IV KITS (Controls & IT)** group; for TomoWISE, the TomoWISE beamline team.

1. **ForMAX and TomoWISE device topology.** What is the Tango device tree (domain/family/member) and the Sardana pool controllers/motors/channels for ForMAX and TomoWISE? These are the CORA-relevant tomography beamlines and have no public device source; this is the decisive gap. (Internal GitLab is unreachable.)
2. **TomoWISE build status and timeline,** and how it relates to the existing CORA TomoWISE deployment-in-design. The index lists it; it is in-design, not operational.
3. **contrast vs Sardana per beamline.** Which beamlines run `contrast` and which run Sardana (and which run both)? This bounds which orchestration layer CORA's edge would replace per beamline.
4. **Fast-path substrate.** Which signals are plain Tango attributes vs direct-socket / PandABox / IcePAP fly-scan triggering? This bounds the ControlPort surface beyond the Tango floor.
5. **SciCat seam.** Is dataset ingestion into SciCat mandatory for MAX IV proposals, and at what point? Is the catalogue open to external users? This decides invert-vs-project.
6. **Identity chain.** Is DUO the authoritative scheduling / access-control chain CORA must read, and via which API?
7. **Identifier mapping.** Confirm the `BnnnX` port IDs and how endstation / branch maps to CORA's run / acquisition-context identifiers.

---

## 8. Source list

**Facility (hardware facts):**
- MAX IV beamlines index: https://www.maxiv.lu.se/beamlines-accelerators/beamlines/
- ForMAX: https://www.maxiv.lu.se/beamlines-accelerators/beamlines/formax/ and /about-formax/
- TomoWISE: https://www.maxiv.lu.se/beamlines-accelerators/beamlines/tomowise/
- DanMAX: https://www.maxiv.lu.se/beamlines-accelerators/beamlines/danmax/
- MAX IV (Wikipedia, roster + ring parameters): https://en.wikipedia.org/wiki/MAX_IV

**Control system (software facts):**
- MaxIV-KitsControls (GitHub org, 94 repos): https://github.com/MaxIV-KitsControls
- sardana-biomax (archived, real BioMAX handle): https://github.com/MaxIV-KitsControls/sardana-biomax
- maxiv-science (GitHub org, contrast + drp-*): https://github.com/maxiv-science
- contrast (DAQ framework, per-beamline real handles): https://github.com/maxiv-science/contrast
- gitlab.com/MaxIV (public mirror of some KITS tooling): https://gitlab.com/MaxIV
- Sardana architecture (Pool / MacroServer / Tango-only protocol): https://sardana-controls.org/devel/overview/overview.html and /users/overview.html

**Data management:**
- SciCat at MAX IV (under Controls & IT): https://www.maxiv.lu.se/beamlines-accelerators/controls-it/it-services/scicat/
- SciCat project (adopter registry): https://www.scicatproject.org
- DUO user-office guides: https://www.maxiv.lu.se/user-access/duo-guides/

**Internal-only (named, not reachable):** `gitlab.maxiv.lu.se` (canonical per-beamline device config + Sardana pool config; NXDOMAIN from public DNS, parent `maxiv.lu.se` and `scicat.maxiv.lu.se` resolve).
