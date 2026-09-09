# Notes

## Techniques

*What CORA would run at I13-1: hard X-ray ptychography and coherent diffraction imaging, a [Catalog](../../catalog/methods.md) Method bound through a [Diamond Practice](../diamond/index.md#the-techniques-adapted-here). It is the fleet's first coherent lensless imaging, and its Capability is new and deferred, the more so because only the coherence-branch endstation is in source.*

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Ptychography / coherent diffraction imaging (CDI) | `ptychography` | a coherent beam is raster-scanned across overlapping points on the sample and the far-field coherent-diffraction pattern is captured at each point; the real-space image is reconstructed downstream. The fleet's first coherent lensless imaging. New Capability, pending (TECH-1) |

The technique is recorded as a pending [Practice](../diamond/index.md#the-techniques-adapted-here) on the Diamond Site, `I13-1_ptychography_practice` (TECH-1).

### The acquisition shape

Ptychography is not a new kind of device, it is a way of acquiring. A coherent beam is rastered across the sample in overlapping points, the [sample stage](sample.md) moving point to point (SAMPLE-1); at each point the Merlin (the Medipix3 photon-counting detector) records the far-field coherent-diffraction pattern; and the stack of diffraction patterns, together with the known scan positions, is enough to reconstruct a real-space image of the sample. The overlap between adjacent points is what makes the reconstruction tractable.

CDI is the same lensless-imaging idea read from far-field coherent diffraction; CORA carries the pair under the one `ptychography` Method (TECH-1).

So the parts in source are a raster `LinearStage` (the PI piezo sample-scanning stage, SAMPLE-1) and two `Camera`s: the Merlin as the science detector that records each diffraction frame, and the Aravis / GenICam side camera for sample alignment (DET-1). The novelty lives in how they are driven and in what happens afterward, not in a new device class.

### Why the Capability is new, and deferred

Ptychography is a genuinely new science Capability for CORA to model as a beamline's purpose. HXN already rasters a coherent nanobeam and reconstructs from the diffraction stack, but as one of several scanning-probe modes; I13-1 is the first beamline CORA models around coherent lensless imaging as its reason for being. CORA carries the `ptychography` Method as pending rather than coining it outright, the same earn-the-abstraction discipline every new-domain technique follows (TECH-1).

It would be tempting to read the novelty as a new device family, a "coherent imaging" class. That is the wrong axis. The coherence is a property of the beam and the acquisition, and the devices that realise it are a raster `LinearStage` and `Camera`s already in the Catalog. The new thing is a Method, an acquisition shape plus a reconstruction, and it adds no Family ([Model](#model)).

The image reconstruction, turning the stack of far-field diffraction patterns into a real-space image, is `ComputePort` work, not a beamline Method. It runs downstream of the acquisition, not on a device on the floor.

### Not modelled yet

This is a deliberately partial first cut, the same posture as the sibling i20-1 scaffold. The public dodal module exposes only the coherence-branch endstation, the sample stage, the side camera, and the Merlin detector. What sits upstream is absent from source and deferred, not invented:

- The shared I13 source and the optics that condition the coherent beam (the undulator, monochromator, mirrors, and slits) are upstream of the endstation and not in the module. They are carried as open questions, not fabricated (SRC-1, OPT-1).
- The machine state is observe-only against a loose `StorageRing`; the shared source is deferred with it (MACHINE-1, SRC-1).
- The PSS search-and-secure permit signals and the photon / front-end shutters are absent from the dodal module and carried pending, not invented (PSS-1).
- Beam-conditioning and shutter conduct paths, and the supporting infrastructure around the endstation, follow once their devices are in source (CTRL-1, SUP-1).

Each of these is named on the [Open questions](#open-questions) page rather than guessed at. The source walk that grounds what is and is not present is the generated [beamline](source.md) view.

## Governance

*Who may act at I13-1 and the trust shape CORA applies. This is CORA's governance design landing on the coherence-branch endstation, not a description of the beamline's current controls authority. Scaffold, not yet instantiated.*

People and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not in the `i13_1` dodal module (GOV-1), so the principals are the design shape, not a registered list. This page follows the same model as the other Diamond beamlines, and the same partial-first-cut posture as the I13-1 scaffold overall: only the coherence-branch endstation is in this cut, and the shared I13 source and optics are deferred (SRC-1, OPT-1).

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the Diamond Site. An I13-1 beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority. The Diamond operator pool and review structure are site-level and shared across the beamlines, so they are not instantiated per beamline; they are carried pending on the [Diamond Site page](../diamond/index.md#safety-and-governance) (GOV-1). None of this is in dodal, which is a controls library, not an organizational record.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may drive the [sample stage](sample.md) through a ptychography raster, arm the [Merlin detector](sample.md) to record the far-field coherent-diffraction pattern, view the sample on the side camera, override a caution, or commit an alignment. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The Diamond proposal and cycle are a fact CORA's Campaign uses for custody.

Because I13-1 is a reverse-engineered scaffold rather than a pilot, the concrete trust shape (the Zone grouping the coherence-branch resources, the Conduit binding the surfaces that may issue commands, and the Policies that say who may do what) is named here, not built. It would land, following the [2-BM governance](../2-bm/governance.md) shape, if and when the deployment approaches real scope.

### The Enclosure I13-1 gates

This cut covers a single enclosure, the grouping CORA's Zone would follow (ENC-1):

| Enclosure | PV zone | What it holds |
| --- | --- | --- |
| `i13-1` | `BL13J` | the coherence-branch experiment hutch: the PI piezo sample-scanning stage, the Aravis / GenICam side camera, and the Merlin / Medipix3 detector |

The shared I13 source and the I13-2 imaging branch are out of this cut and not part of the Zone here (SRC-1, OPT-1).

### The safety tier behind the beam

The safety tier behind the beam is the personnel safety system. The leaves that must be satisfied before the beam can enter an enclosure are the PSS search-and-secure permit signals, and the photon and front-end shutters are what those leaves gate. Both the permit signals and the shutters are absent from the `i13_1` dodal module, so CORA does not name them and does not invent them: the Enclosure permit signals and the shutters are carried pending (PSS-1). When staff confirm the signal and shutter handles, they bind to the Enclosure as the permit leaves the way the Diamond siblings carry theirs. No interlock, PSS, or equipment-protection tier is invented in the meantime.

Clearances (the safety forms that must be active to start) are issued at the Diamond Site, not on the beamline, and the beamline links up to them rather than restating them (GOV-1). The Diamond PSS clearance is carried pending because its form names are not confirmed (PSS-1).

### Coherent imaging under custody

I13-1's reason for existing is coherent lensless imaging: a ptychography or coherent-diffraction-imaging acquisition raster-scans the coherent beam across the sample and records the far-field diffraction, and a real-space image is reconstructed from that diffraction stack. In CORA's model this novelty is an acquisition shape and a reconstruction, a Method, not a new device class (TECH-1); the devices it gates are a raster LinearStage and Cameras (SAMPLE-1, DET-1), and the reconstruction is ComputePort work, not a beamline device. That makes the repeated raster acquisition the place CORA's custody and trust shapes would earn their keep: the trust boundary bounds who may drive the raster and arm the Merlin detector, and the Campaign and Subject shapes carry the sample's custody and the diffraction record.

If an autonomous Agent were added (for example to step the raster or decide when a diffraction stack is complete enough to reconstruct), it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet; with the shared source and optics deferred and the ptychography Method carried pending (SRC-1, OPT-1, TECH-1), this stays design intent.

### What is deliberately not modelled

- **The PSS permit signals and shutters (PSS-1).** Absent from the `i13_1` dodal module, carried pending, not invented.
- **The Diamond operator pool and review structure (GOV-1).** Site-level and shared across the beamlines, carried pending on the Diamond Site, not instantiated per beamline.
- **The shared I13 source and optics (SRC-1, OPT-1).** Upstream and absent from the module; deferred, not invented. No monochromator, mirror, slit, or undulator Asset is coined.
- **The concrete Zone, Conduit, and Policy instances.** Named as the trust shape, not built; they would land if and when the deployment approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

The full delete-on-answer queue is on [Open questions](#open-questions); where each device and Method lands is on [Model](#model).

## Model

*The developer's by-kind index: where each CORA aggregate's I13-1 content lives, why coherent imaging coins no new family, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at I13-1 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes I13-1 new

I13-1 is CORA's first coherent lensless-imaging beamline. The fleet has tomography, XRF microprobe, and a hard X-ray nanoprobe (HXN), but no ptychography or coherent diffraction imaging (CDI). Ptychography raster-scans a coherent illumination across overlapping points on the sample and records a far-field coherent-diffraction pattern at each point; the real-space image is reconstructed downstream from the diffraction stack. That is the novelty, and it is an **acquisition shape plus a reconstruction**, a new Capability deferred as a pending Method (`TECH-1`), not a new device class.

### No new families

The scout that surfaced I13-1 anticipated a new "coherent imaging" device family. That is the wrong axis: coherent imaging is a Method, not a device. The devices the technique needs are a sample-scanning stage and an area detector, both of which the catalog already covers, so I13-1 coins no new Family and changes nothing in the catalog:

- **The piezo sample-scanning stage binds the catalog `LinearStage`.** The ptychography raster is its operative motion; the fixed-angle lab-frame variant (`BL13J-MO-PI-02:FIXANG:`) is a setting on the same stage, not a separate device class (`SAMPLE-1`).
- **The Merlin photon-counting detector and the side viewing camera bind the catalog `Camera`.** The Merlin records the far-field coherent-diffraction pattern (the science detector); the side camera is for alignment (`DET-1`).
- **The machine state binds the loose `StorageRing`** (`MACHINE-1`).

The coherent imaging itself is the `ptychography` Method, the fleet's first, carried pending (`TECH-1`).

### Deliberately not here yet

- **The shared I13 source and optics (`SRC-1`, `OPT-1`).** The dodal `i13_1` module exposes only the coherence-branch endstation; the undulator, monochromator, mirrors, and slits are upstream and not in the module, so they are deferred, not invented. This is the same partial-first-cut posture as I20-1.
- **The ptychography Method and the reconstruction.** Whether ptychography / CDI enters CORA's catalog as a Capability / Method is an owner decision; the Practice renders unlinked, pending (`TECH-1`). The image reconstruction from the diffraction stack is `ComputePort` work, not a beamline device.
- **The simulated devices and full asset-tree scenarios.** No `test_i13_1_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the I13-1 team to confirm before the model can be trusted.*

I13-1 was reverse-engineered from the beamline's own bluesky device layer ([DiamondLightSource/dodal](https://github.com/DiamondLightSource/dodal), `src/dodal/beamlines/i13_1.py`), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from dodal rather than confirmed by staff. This is a **deliberately partial** first cut: dodal currently exposes only the coherence-branch endstation, so the shared I13 source and optics are deferred, not invented. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Is I13-1 its own experiment hutch, and how does it relate to the I13-2 imaging branch and the shared I13 source? | One `i13-1` experiment hutch on the `BL13J` prefix. | The Enclosure grouping. |
| SRC-1 | Blocks-go-live | The shared I13 undulator source, absent from the i13_1 dodal module. | An undulator upstream, not modelled in this partial cut. | The source Asset. |
| OPT-1 | Blocks-go-live | The shared I13 optics (monochromator, mirrors, slits), absent from the i13_1 dodal module. | Shared optics upstream, not modelled in this partial cut. | The optics Assets. |

### Endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The piezo sample-scanning stage axes, and the fixed-angle lab-frame variant (`BL13J-MO-PI-02:FIXANG:`): one stage with two reference frames or two stages? | One `LinearStage` (the ptychography raster); the fixed-angle frame a setting on the same stage. | The sample-stage modelling. |
| DET-1 | Blocks-go-live | The Merlin (Medipix3) detector configuration and the side viewing camera role. | The Merlin and the side camera bind `Camera`; the Merlin is the coherent-diffraction science detector. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from dodal current and correct? | The handles in the descriptor are taken from dodal and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the photon / front-end shutters (absent from the i13_1 dodal module). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| MACHINE-1 | Nice-to-have | The storage-ring state I13-1 reads. | Observe-only machine state, a loose `StorageRing`; the exact PVs pending. | The machine-state observation. |
| SUP-1 | Nice-to-have | The vacuum extent of the coherent-beam path. | Photon beam, cooling water, and vacuum on the flight path. | The Supply observations. |
| GOV-1 | Nice-to-have | The Diamond operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the Diamond Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Does ptychography / coherent diffraction imaging enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice; the fleet's first coherent diffractive imaging, no `cora.capability.ptychography` coined. | The ptychography Capability. |
