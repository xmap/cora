# Notes

## Techniques

*What CORA would run at CDI: coherent-imaging techniques, each a [Catalog](../../catalog/methods.md) Method. CDI follows the deferral the coherent and scanning beamlines set, after Diamond [i13-1](../i13-1/notes.md#techniques), which opened the pending `ptychography` Method, and APS [8-ID](../8-id/notes.md#techniques), [CHX](../chx/notes.md#techniques), and [HXN](../hxn/notes.md#techniques).*

CDI's techniques are coherent diffractive imaging: focus a coherent beam, record the far-field diffraction pattern, and recover the real-space image offline by phase retrieval. These Methods are new to CORA's imaging- and spectroscopy-heritage catalog, so the Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Ptychography | `ptychography` | a scan of overlapping coherent-diffraction frames across the sample; reuses the pending `ptychography` Method Diamond i13-1 opened; the reconstruction is a `ComputePort` leg, not a beamline Method (the HXN framing) |
| Forward CDI | `coherent_diffraction_imaging` | a single far-field coherent-diffraction frame on the Eiger2 / Merlin from an isolated object; the single-shot variant of the same deferred coherent-imaging cohort, not separately coined |
| Bragg CDI | `coherent_diffraction_imaging` | a rocking series around a Bragg peak for strain imaging of a crystalline grain, with the [goniometer](sample.md) setting the orientation; the same deferred coherent-imaging cohort |
| Alignment | [`alignment`](../../catalog/methods.md) | beam, KB, mirror, and slit tuning; reuses the existing Method |

All three imaging techniques need the [KB nanofocus and sample stack](sample.md) and the [coherent detectors](detector.md); how the exposure is gated on the floor is the open timing question (TIMING-1).

### Why the Methods stay deferred

Diamond i13-1 opened the coherent-imaging Method as the pending `ptychography` Method (the fleet's first coherent diffractive imaging), carried pending until a conduct-path earns it (TECH-1). CDI reinforces that Method at a second facility and adds the single-shot forward and Bragg CDI variants, which are not separately coined; the concrete acquisition recipes (frame counts, scan grids, rocking ranges, exposures) join as the deployment approaches the point where CORA drives the beamline. This is the same earn-the-abstraction discipline the deferred `small_angle_scattering` (8-ID, CHX) techniques follow. Because the full coherent-imaging Method scope is not in the catalog, CDI records **no Practice** in the [NSLS-II Site](../nsls2/index.md), as CHX records none for its coherent-scattering Methods; the binding lands when the Method does.

The phase retrieval itself (the iterative reconstruction that turns the diffraction frames into a real-space image, and the ptychographic engine that solves for object and probe together) is `ComputePort` work, not a beamline Method. This is the imaging analogue of CHX's correlation analysis: the beamline takes the frames, CORA's compute leg turns them into the result.

## Governance

*Who may act at CDI and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. A CDI beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may align the KB nanofocus, change the incident energy, arm a ptychographic scan, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

### Long unattended scans

A ptychographic map or a Bragg-CDI rocking series can run long and unattended, which is where CORA's trust shape earns its keep: the engine holds the scan while the trust boundary bounds what may change mid-acquisition and who may intervene. If an autonomous Agent were added to steer acquisition (choose the next scan region, decide when the diffraction signal is sufficient, trigger a reconstruction to check convergence), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.

## Model

*The developer's by-kind index: where each CORA aggregate's CDI content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at CDI |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [the stage pages](source.md) (`EnergyAxis`) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (9-ID-A optics, 9-ID-C endstation) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring CHX, HXN, and the other reverse-engineered deployments. Left out on purpose:

- **No new Family.** CDI is a reuse-and-reinforce deployment: the area detectors and diagnostic cameras bind `Camera`, the foil intensity monitor `FluxMonitor`, the pre-mirrors and the KB nanofocus pair `Mirror`, both monochromators `Monochromator`, the sample stack `Goniometer`, the white-beam / branch / conditioning slits `Slit`, the attenuator foils `Filter`, the undulator `InsertionDevice`, the master energy a `PseudoAxis`, and the endstation towers `LinearStage`. Nothing graduates and the catalog is unchanged.
- **The diagnostics and supply readback.** The `DiamondBeamMonitor` binds the graduated catalog `PositionMonitor` Family, which presents the `Sensor` Role, earned across the wide fleet that shares it, distinct from `FluxMonitor` by measuring beam position rather than flux. The `StorageRing` current readback is a loose supply observation (machine state), never an Asset Family.
- **No new Capability or Method.** Ptychography reuses the pending `ptychography` Method Diamond i13-1 opened (the fleet's first coherent diffractive imaging); forward and Bragg CDI are the single-shot variants of the same deferred coherent-imaging cohort, not separately coined (`TECH-1`). CDI reinforces the Method without coining anything and records no Practice until the scope lands. The phase retrieval and ptychographic reconstruction are `ComputePort` work, not a Method.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the CDI team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/cdi-profile-collection`](https://github.com/NSLS2/cdi-profile-collection) profile collection and the [`NSLS2/cditools`](https://github.com/NSLS2/cditools) device library): the EPICS PVs are read from them, but vendor identities, physical positions, and the timing configuration are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | IVU18 undulator period, gap range, and harmonic usage. The device (`SR:C09-ID:G1{IVU18:1}`) is confirmed. | An in-vacuum undulator, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs and the photon-shutter PVs. Neither is in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | Whether the 09IDB branch zone (`Slt:DM3`, the quadrant BPM) is a distinct access-gated enclosure or part of the optics hutch. | Two enclosures (9-ID-A optics, 9-ID-C endstation); 09IDB folded into the optics zone. | The Enclosure boundaries. |
| MACHINE-1 | Nice-to-have | The storage-ring state CDI reads (current, fill, status). | Observe-only machine state, a loose `StorageRing`; the exact PVs beyond `ring_current` pending. | The machine-state observation. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the NSLS-II Site, not instantiated per beamline. | The governance principals. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The Si DCM cryo detail and full range (the Si(111) reflection and `d = 3.1287 A` are read from the Energy model), and the DMM multilayer coating and bandpass. Both monochromators (`Mono:HDCM`, `Mono:DMM`) are in source. | Two Monochromator Assets, Si(111) recorded, other settings blank. | The Monochromator settings. |
| KB-1 | Blocks-go-live | The KB mirror focal size, coating / stripe, and working distance; whether both VKB and HKB are always installed. | A `Mirror` Asset (the KB pair); focus geometry blank. | The KB nanofocus spec. |
| ENERGY-1 | Nice-to-have | Whether incident energy is ever scanned as the measurement, and the true energy range (the `5-15 keV` bounds are marked `TODO: CHECK` in source). | Fixed-energy imaging; the range left provisional. | The energy Capability decision. |

### Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | Which endstation tower (`TDMS:T1` / `TDMS:T2`) carries the sample versus the detector, the sample-to-detector distance that sets the q-range, and the full `Gon:1` goniometer axis set. Some tower axes are read-only pending commissioning in source. | Two `LinearStage` towers and a `Goniometer`; roles and distance deferred. | The endstation geometry. |
| DET-1 | Blocks-go-live | Which detector (Eiger2 / Merlin) is primary for which technique, the foil materials / thicknesses, and whether a direct-beam beamstop is installed (none is in source). | Both Cameras; Eiger2 primary; no beamstop modelled. | The detector roster and beamstop. |
| CAM-1 | Nice-to-have | Which diagnostic cameras (the BCU inline camera, the sample camera, the optics-module Prosilicas) are live. | The inline and sample cameras modelled; others noted. | The diagnostic-camera set. |
| DIAG-1 | Nice-to-have | The foil-monitor channel map and the quadrant / diamond BPM channels (the diamond BPM was repurposed from ion-chamber use in source). | Read-only flux and beam-position probes; channel maps blank. | The `FluxMonitor` and `PositionMonitor` bindings. |

### Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TIMING-1 | Blocks-go-live | The exposure-gating chain. The profile collection exposes no trigger box (no Zebra / PandA startup file, no shutter PVs); the Eiger2 and Merlin carry internal and external trigger modes. How is a coherent-imaging exposure gated and synchronized with the scan? | Detector-internal triggering; no floor trigger box modelled. | The triggering chain. |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, IPs behind the EPICS motor records. | One `MotionController` family bound (`EndstationMotionController`), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the coherent-imaging Methods (forward CDI, ptychography, Bragg CDI) enter CORA's catalog, or stay deferred? This is the same owner-scope decision 8-ID opened. | Methods deferred (rendered unlinked), no Practice recorded. | The coherent-imaging Method scope. |
