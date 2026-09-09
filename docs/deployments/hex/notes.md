# Notes

## Techniques

*What the modelled part of HEX is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md#the-techniques-adapted-here) is how a facility adapts it. HEX measures engineering-materials and energy-storage samples three ways, all in the single operational endstation and all at high X-ray energy: X-ray imaging and tomography, energy-dispersive X-ray diffraction (EDXD), and angle-dispersive / powder diffraction (ADXD). One of those, tomography, is a Method CORA already holds; the rest render unlinked and are carried pending until the owner-scope decision (`TECH-1`) brings them into the catalog.

HEX is mostly reinforcement of imaging and high-energy diffraction the fleet already speaks. Read this page for the one thing that is structurally distinct: all three techniques run in the same experiment, with detectors and optics moved into the beam remotely.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray tomography and CT | `tomography` | high-energy white-beam and monochromatic tomography (continuous fly-rotation, `tomo_flyscan`) on the [Kinetix sCMOS cameras](detector.md); reuses the graduated Method (shared with [2-BM](../2-bm/techniques.md) and [FXI](../fxi/notes.md#techniques)) |
| Time-resolved radiography | `radiography` | 2D high-speed / in-situ radiography on the [Phantom Veo](detector.md); shares the Method APS [7-BM](../7-bm/notes.md#techniques) left pending (`TECH-1`) |
| Energy-dispersive diffraction (EDXD) | `energy_dispersive_diffraction` | spatially-resolved EDXD on the [GeRM germanium strip detector](detector.md); shares the Method 7-BM left pending, HEX the second consumer (`TECH-1`) |
| Angle-dispersive / powder diffraction (ADXD) | `powder_diffraction` | monochromatic area-detector diffraction on the [PerkinElmer flat panel](detector.md); shares the Method Diamond [i11](../i11/notes.md#techniques) left pending, HEX the second consumer (`TECH-1`) |

All four techniques need the [incident-beam chain](source.md) (the superconducting wiggler, the low-energy filters, and the monochromator for the monochromatic modes), the [sample stack](sample.md) (the 500 kg sample tower, the tomographic rotation and translations), and the [endstation detectors](detector.md). The white beam serves high-speed imaging and EDXD; the monochromatic beam serves tomography at a chosen energy and angle-dispersive diffraction.

### The imaging and diffraction is reinforcement, not novelty

Tomography, radiography, and high-energy diffraction overlap the fleet. Tomography is the operational pilot's defining technique ([2-BM](../2-bm/techniques.md)) and is graduated in the catalog; the [FXI](../fxi/notes.md#techniques) full-field microscope is a second tomography sibling. Energy-dispersive diffraction is the pending APS [7-BM](../7-bm/notes.md#techniques) white-beam Method, and angle-dispersive / powder diffraction is the pending Diamond [i11](../i11/notes.md#techniques) Method. HEX reuses the same `Camera` / `Scintillator` / `RotaryStage` / `LinearStage` / `EnergyDispersiveSpectrometer` vocabulary, coins no new Family, and adds a second consumer to each pending diffraction Method.

So the technique side of HEX earns no new abstraction. It reinforces, at a high-energy beamline, the case that energy-dispersive and powder diffraction belong in the catalog (`TECH-1`), the same earn-the-abstraction discipline 7-BM and i11 already follow. The device Roles exist (the cameras and the flat panel present Detector, the GeRM strip detector presents Sensor), so what stays pending is the science Capability, not a device shape. Because those Capabilities are not yet in the catalog, the matching Site Practices (`HEX_radiography_practice`, `HEX_energy_dispersive_diffraction_practice`, `HEX_powder_diffraction_practice`) are carried pending in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here); each binding lands when its Capability does. `HEX_tomography_practice` names the graduated `tomography` Method and renders linked.

### Multi-technique in one experiment, the distinct contribution

The structurally distinct thing about HEX is not any one technique; it is that imaging / tomography, EDXD, and ADXD are all available in the single F-hutch endstation during the same experiment, with detectors and optics moved into place remotely per technique. A high-energy beamline lets a user follow a working battery or a loaded engineering component and switch, within one mounting, between a tomographic view of the microstructure, an energy-dispersive map of internal strain and phase, and an angle-dispersive powder pattern.

CORA models this as **multiple Methods over one endstation**, not a new Capability. The switch itself is a positioning action: a [detector / optics stage](detector.md) moves the chosen detector into the beam. That positioning binds the catalog `LinearStage` and is conducted over the `ControlPort` (see [Controls](controls.md)); it is a Practice-level sequence, not a new technique. The one-technique-per-acquisition assumption is what this stresses, and the resolution is that a Run selects its technique by positioning, then acquires (`TECH-1`).

| Technique in the experiment | Detector | Family |
| --- | --- | --- |
| imaging / tomography | [Kinetix sCMOS](detector.md) + scintillator-lens | `Camera` + `Scintillator` |
| time-resolved radiography | [Phantom Veo](detector.md) | `Camera` |
| energy-dispersive diffraction (EDXD) | [GeRM strip detector](detector.md) | `EnergyDispersiveSpectrometer` |
| angle-dispersive diffraction (ADXD) | [PerkinElmer flat panel](detector.md) | `Camera` |

### Not modelled yet

The concrete acquisition recipes are not written yet. For tomography that is the fly-rotation step model, the dark / flat sequence (`tomo_dark_flat`), and the vertical stitch (`tomo_y_scan_loop`); the reconstruction (flat-field correction, ring / stripe removal) is `ComputePort` work, not a beamline Method. For diffraction it is the EDXD gauge-volume definition and the angle-dispersive integration that turns 2D frames into one-dimensional patterns. These join as the deployment approaches the point where CORA drives HEX.

Whether any of these techniques enters CORA's catalog is an owner-scope decision on [Model](#model): a modelling exercise reinforces the case but does not mint cross-facility Method vocabulary on its own. HEX adds a second consumer to the pending `energy_dispersive_diffraction`, `radiography`, and `powder_diffraction` Methods, which strengthens the case for cataloging them but leaves that an owner decision (`TECH-1`). See [Open questions](#open-questions) for the world-facts to confirm first, including whether pair-distribution-function (PDF) or three-dimensional X-ray diffraction (3DXRD) are offered, which public sources do not list for HEX (`TECH-1`).

## Governance

*Who will act at HEX, and the trust shape that will gate it. First cut.*

Governance at HEX follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

HEX is not yet driven by CORA, so this shape is not yet instantiated. As a modelling-exercise scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. The profile collection exposes only coarse queue-server groups, not the human roster, so the NSLS-II operator pool and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md#safety-and-governance), shared with the rest of the fleet (`GOV-1`).

### A distinct allocation policy

HEX has one governance fact the other NSLS-II beamlines do not: a share of its beamtime is reserved for proposals aligned with New York clean-energy and energy-storage goals. Public sources describe a portion of beamtime set aside for such proposals, evaluated by a dedicated proposal-evaluation committee on weighted criteria (technical merit, New York commercial relevance, economic development, and personnel), with the remainder allocated through the standard NSLS-II proposal review and all proposals administered through the facility proposal system. This is a real, distinct trust-shape input: an allocation Policy that gates which experiments run, layered on top of the facility-wide safety and access tiers.

CORA records this as a Policy-level fact, not a new bounded context or descriptor. The exact reservation fraction and the committee's scoring split are carried as a world-fact (`GOV-1`) and are modelled when CORA drives the beamline, not instantiated now. The allocation Policy binds to the NSLS-II operator and review roles carried pending at the Site.

### The safety boundary

The safety tier is the other piece that is not yet settled. The PSS search-and-secure permit signals and the front-end and photon shutters are absent from the beamline's profile collection, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

HEX adds the hazard classes that come with its instruments. Those land with the equipment that brings them, and an experiment Clearance would carry them.

| Hazard class | Where it lands | Tracking |
| --- | --- | --- |
| High-energy hard X-ray beam (white to 250 keV, monochromatic to 200 keV) | the [optics](index.md) and [endstation](index.md) enclosures (`hex-foe`, `hex-endstation`) | (`PSS-1`, `SCW-1`) |
| The superconducting wiggler source | the [Source](source.md) walk (cryogen-free, no liquid-helium hazard) | (`SCW-1`) |
| Heavy-sample handling (up to 500 kg) | the [Sample](sample.md) tower | (`STAGE-1`) |
| User-brought in-situ / operando environments | the [Sample](sample.md) endstation | (`INSITU-1`) |

The high-energy beam is the interlocked hazard, and at these photon energies the shielding burden is heavier than the fleet's lower-energy beamlines; its permit leaves stay pending until the PSS signals are confirmed (`PSS-1`). The superconducting wiggler is cryogen-free, so no liquid-helium supply hazard is carried (`SCW-1`). The heavy-sample handling and the user-brought in-situ environments are operational hazards carried with the equipment that brings them (`STAGE-1`, `INSITU-1`); none is invented, each is recorded against its question.

### When the shape lands

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives HEX, following the [2-BM governance](../2-bm/governance.md) shape. Because HEX shares the NSLS-II EPICS and ophyd floor with its siblings, it re-tests the Site and Federation kernel rather than introducing a new trust model. The Zone groups the same optics and endstation resources the [inventory](index.md) lists; the Conduit binds the command surfaces; the Policies bind to the NSLS-II operator roles carried pending at the Site, with the NYSERDA-aligned allocation Policy layered on top (`GOV-1`).

## Model

*The developer's by-kind index: where each CORA aggregate's HEX content lives, how it models the multi-technique endstation and the heavy sample tower, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at HEX |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the incident-energy `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes HEX new

The honest answer is: not much on any single technique, and three real things on structure. HEX measures engineering-materials and energy-storage samples by high-energy imaging / tomography, energy-dispersive diffraction (EDXD), and angle-dispersive / powder diffraction (ADXD). The imaging overlaps the fleet heavily (the 2-BM pilot, the NSLS-II FXI), and the diffraction reuses the pending energy-dispersive (7-BM) and powder (i11) Methods. That side reuses the existing `Camera` / `Scintillator` / `RotaryStage` / `LinearStage` / `EnergyDispersiveSpectrometer` / `InsertionDevice` / `Monochromator` / `Filter` vocabulary and contributes reinforcement, not novelty.

HEX's three genuinely distinct contributions are:

- **Multi-technique in one experiment.** All three techniques run in the single F-hutch endstation during one experiment, with detectors and optics moved into the beam remotely. CORA models this as multiple Methods over one endstation, the technique switch a positioning leg over the `ControlPort`, not a new Capability (`TECH-1`).
- **Very large and heavy engineering samples.** The 500 kg removable sample tower is a heavy reconfigurable fixture, not a precision goniometer. It reuses `Table` + `RotaryStage` + `LinearStage` with capacity and the configuration set as settings (`STAGE-1`).
- **A high-energy hard X-ray source.** The superconducting wiggler (4.3 T, 70 mm period) reaching 200 keV monochromatic is a first for the fleet. It binds the existing `InsertionDevice` Family, with the field and energy reach as source specs (`SCW-1`).

### No new families

HEX coins no new Family and changes nothing in the catalog.

- **The superconducting wiggler binds `InsertionDevice`** (the undulator precedent at the NSLS-II siblings). The beam mode (white 30 to 250 keV versus monochromatic 30 to 200 keV) is selected by inserting or retracting the monochromator first crystal, so it is a setting on the optic, not a second source (`MONO-2`).
- **The optics reuse:** the low-energy filters bind `Filter`; the bent-Laue monochromator binds `Monochromator` (a Bragg optic, not the soft X-ray `GratingMonochromator`); the incident energy is a `PseudoAxis` over it; the front-end slits bind `Slit`.
- **The sample side reuses:** the tomographic rotation binds `RotaryStage`; the sample translations bind `LinearStage`; the 500 kg removable tower binds `Table`.
- **The detection side reuses:** the Kinetix sCMOS and Phantom Veo cameras and the PerkinElmer flat panel bind `Camera`; the imaging scintillator-lens table binds `Scintillator`; the detector / optics positioning binds `LinearStage`; the GeRM germanium strip detector binds the existing `EnergyDispersiveSpectrometer` Family (below).

### The GeRM strip detector reuses an earned family

The one place HEX looks like it might force a new abstraction is its energy-dispersive detector, the GeRM germanium strip detector that produces a per-channel energy spectrum rather than a 2D frame. That shape is already in the catalog: the `EnergyDispersiveSpectrometer` Family was earned by the APS 2-ID fluorescence detector and the 7-BM germanium energy-dispersive-diffraction detector, and its definition presents the `Sensor` Role (a scalar or short-vector Reading per point) and explicitly spans the silicon-drift and germanium variants. HEX's GeRM detector is the **third consumer** of that Family, with channel count and energy resolution per-Asset settings. So EDXD on HEX is a reuse, not a graduation, and no catalog or loose-family change is forced (`DET-2`).

### How the multi-technique switch is modelled (no new capability)

The F-hutch offers imaging / tomography, EDXD, and ADXD in one experiment. CORA models the switch between them as a **positioning action over existing devices**, not a new Capability or device:

- each technique has its detector already on the [detection](detector.md) side (the Kinetix cameras, the PerkinElmer flat panel, the GeRM strip detector);
- a `LinearStage` (`DetectorStage`) moves the chosen detector or optic into the beam;
- CORA conducts that positioning over the `ControlPort`, then runs the technique's Method.

So the "multi-technique endstation" is a Practice-level sequence, not a fused mega-instrument. The stress it puts on the model, that a single endstation hosts several one-technique acquisitions selected by positioning, is resolved by treating technique selection as a conducted positioning leg ahead of acquisition (`TECH-1`). No new family is coined for the switch.

### Deliberately not here yet

- **The B / C / D / E hutch contents (`ENC-1`, `LAYOUT-1`).** HEX is designed for six enclosures (A = FOE, B, C, D, E, F). All six are declared in the descriptor, forward-looking, but only the operational FOE (`hex-foe`) and F-hutch (`hex-endstation`) carry devices; B (not erected) and C / D / E (future-upgrade shells) are declared as device-free enclosures and carry no Assets in this cut. The descriptor validates that every device's enclosure ref is declared but allows an unreferenced enclosure, so the shells are honest forward-looking placeholders, not invented contents. The satellite-building identity and the per-hutch positions are carried as world-facts (`SAT-1`, `LAYOUT-1`).
- **The monochromatic focusing optic (`FOCUS-1`).** The beamline page lists focusing for the monochromatic beam as "being commissioned." It is not yet modelled as a device; what optic it is and its target spot are carried as a world-fact.
- **In-situ sample environments (`INSITU-1`).** HEX's science is operando battery and engineering-materials work, but no specific rig (load frame, furnace, cryostat, battery cycler) is source-confirmed as installed; the endstation is "capable of housing" user-brought environments. Per earn-the-abstraction, no in-situ rig is modelled as an Asset in this cut. If a specific rig is confirmed installed and a second fleet beamline brings one, that is the trigger to consider a sample-environment Family.
- **The heavy-sample stage as a distinct family (`STAGE-1`).** The 500 kg removable tower stresses the assumption that a sample-orientation Asset is small and goniometer-like. CORA holds the line: capacity and the configuration set (configs A to D) are settings on a reused `Table` + `RotaryStage` + `LinearStage`, not a new `HeavyStage` Family. A second fleet beamline with a heavy removable tower would be the rule-of-three trigger.
- **The diffraction Methods.** Whether energy-dispersive diffraction, radiography, and powder diffraction enter CORA's catalog as Capabilities / Methods is an owner decision; the Practices render unlinked, pending. EDXD and radiography are shared with 7-BM and powder diffraction with i11 (`TECH-1`).
- **Pair-distribution-function and 3DXRD.** Public sources do not list PDF (that is NSLS-II 28-ID / [XPD](../xpd/index.md)) or three-dimensional X-ray diffraction for HEX, so neither is modelled or assumed (`TECH-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_hex_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the HEX team to confirm before the model can be trusted.*

HEX was reverse-engineered from public sources (the BNL beamline page, the [beamline 27-ID wiki](https://wiki-nsls2.bnl.gov/beamline27ID), and the beamline's bluesky profile collection [NSLS2/hex-profile-collection](https://github.com/NSLS2/hex-profile-collection) and [NSLS2/hextools](https://github.com/NSLS2/hextools)), so the control handles on the [device pages](index.md) are read from public config rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are the six designed enclosures A (FOE), B, C, D, E, F, with only A and F presently relevant to operations (B not erected; C / D / E future-upgrade shells)? | All six declared; `hex-foe` and `hex-endstation` carry devices, B to E are device-free forward-looking shells. | The Enclosure grouping and the future-hutch contents. |
| SAT-1 | Nice-to-have | Is the satellite building housing the F-hutch the same as Bldg. 742 or a separate numbered structure adjacent to it? | The F-hutch is a distinct enclosure adjacent to Bldg. 742, bound to the NSLS-II Site. | The endstation Enclosure detail. |
| LAYOUT-1 | Nice-to-have | The source-to-F-hutch distance (about 100 m) and whether an exact per-hutch z-position table exists. | About 100 m source to endstation; no per-hutch z table carried. | The beam-path geometry. |
| BRANCH-1 | Nice-to-have | Do the inboard and outboard front-end branches carry any installed optics, or are they bare provisions for the future hutches? | Provisions only; only the center branch carries devices. | The front-end slit modelling. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state HEX reads (current, fill, status). | Observe-only machine state, a loose `StorageRing`; the exact PVs pending. | The machine-state observation. |
| SCW-1 | Nice-to-have | The superconducting wiggler pole count and critical photon energy (only the 4.3 T field, 70 mm period, 1.2 m length, cell-27 straight are published). | An `InsertionDevice` Asset; field, period, and length carried as specs; pole count and critical energy pending. | The source Asset detail. |
| MONO-1 | Blocks-go-live | The monochromator crystal material and geometry (is it Si(111) bent Laue?), the crystal count, and the d-spacing. | A single bent-Laue first crystal on a vertical translation, binding `Monochromator`; the incident energy a `PseudoAxis` over it. | The monochromator and incident-energy Assets. |
| MONO-2 | Blocks-build | The upper monochromatic energy: 150 keV (the wiki) or 200 keV (peer-reviewed, "first NSLS-II beamline to reach 200 keV mono")? | 30 to 200 keV monochromatic, 30 to 250 keV white. | The energy-axis range bound. |
| FILT-1 | Nice-to-have | The FOE low-energy filter materials and thicknesses per branch (center SiC 3 / 6 / 9 / 12 mm; outboard / inboard Cu plus SiC) and the 35 mm pitch. | Beam-hardening filters bound to `Filter`; materials and thicknesses as listed on the commissioning wiki. | The filter Asset detail. |
| FOCUS-1 | Nice-to-have | What focusing optic is being commissioned for the monochromatic beam, and the target focused spot. | Focusing not yet a device; carried deferred. | The focusing-optic Asset. |

### Sample

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The modular sample-tower configurations (A to D), the 500 kg capacity, and which axes are motorized (the tomographic rotation and the translations). | One reconfigurable tower (`Table`, 500 kg, configs A to D) plus a `RotaryStage` rotation and `LinearStage` translations; capacity and config set as settings. | The sample-stage modelling. |
| INSITU-1 | Blocks-go-live | Which in-situ rigs are actually installed or available at the endstation (load frames, furnaces, cryostats, battery cyclers)? | None installed; the endstation is "capable of housing" user-brought environments, so no in-situ rig is modelled. | The sample-environment modelling; the CORA family decision is on [Model](#deliberately-not-here-yet). |

### Detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The PerkinElmer area-detector model (XRD1621?), its pixel count, and that it is the angle-dispersive / powder-diffraction (ADXD) detector. | A PerkinElmer XRD1621 flat panel binding `Camera`, inferred to be the ADXD detector. | The area-detector modelling. |
| DET-2 | Blocks-go-live | The GeRM germanium strip detector channel count, energy resolution, and the EDXD gauge-volume dimensions. | A GeRM strip detector binding the existing `EnergyDispersiveSpectrometer` Family; specs pending. | The energy-dispersive-detector modelling. |
| DET-3 | Nice-to-have | Which Kinetix camera is the tomography default, and the scintillator / lens magnification options behind the "2 & 4 mm", "20 & 40 mm", and "Dual cam" imaging-table positions. | `kinetix1` is the default; the scintillator-lens table binds `Scintillator`; the Phantom Veo is the high-speed camera. | The imaging-camera and scintillator modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the profile collection current and correct, and what are the FOE-optics PVs (absent from it)? | The endstation detector handles are from the profile collection and carried confirm; the FOE-optics PVs are pending. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the photon / front-end shutters (absent from the profile collection). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (the FOE optics) and the cooling supply. | Photon beam, cooling water, and vacuum on the FOE optics; the cryogen-free wiggler draws no liquid helium. | The Supply observations. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure (site-level), and the NYSERDA-aligned beamtime-reservation fraction and the proposal-evaluation committee's scoring split. | Carried pending on the NSLS-II Site; the NYSERDA allocation Policy layered on top, fraction and scoring pending. | The governance principals and allocation Policy. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Is the operational technique set exactly imaging / tomography, radiography, EDXD, and powder / ADXD, with all three diffraction-and-imaging modes available in the one endstation, and are PDF and 3DXRD not offered? | Those techniques only; multi-technique in one endstation via detector / optics positioning; no PDF, no 3DXRD. | The technique Capabilities and the multi-technique modelling. |
