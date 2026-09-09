# Notes

## Techniques

*What i24 is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md) is how a facility adapts it. i24 is the first serial / fixed-target macromolecular-crystallography beamline CORA has looked at, so its technique is a new acquisition shape over the spine, not a recipe over Methods that already exist. Whether it enters the catalog as a Capability is an open question (SSX-1); the function view below survives the eventual vocabulary choice.

| Technique | Beam | Detector | Status in CORA |
| --- | --- | --- | --- |
| Fixed-target serial crystallography | monochromatic, focused | `Eiger` (Detector Role) | a new `serial_crystallography` Capability binding the chip stage + Eiger + sample shutter + Zebra, deferred (SSX-1) |
| Chip raster fly-collection | monochromatic, focused | `Eiger` + `OnAxisViewer` | the acquisition primitive of the technique above: window-addressed, Zebra-gated, no rotation (SSX-1, CHIP-1) |
| Pump-probe excitation | monochromatic, focused | `Eiger` | PMAC-fired lasers on encoder edges; modelled as a trigger setting or a hazard, deferred (LASER-1) |
| Jungfrau commissioning collection | monochromatic, focused | `Jungfrau` (Detector Role) | the same shape on the commissioning detector; carried pending (DET-1) |

A few points of intent shape the model:

- **Serial collection is a new acquisition shape, not a new device.** Rotation MX at I03 sweeps the goniometer omega while the Eiger captures frames through a continuous oscillation: one crystal, one trajectory of angles. i24 does the opposite. The chip stage rasters a fixed-target chip of thousands of static crystals across the beam, and the detector takes one diffraction snapshot per addressable window, with no goniometer rotation at all. The dataset is many single-orientation patterns, indexed and merged downstream, rather than one rotation sweep. The device Roles already exist (the chip stage presents Positioner, the Eiger presents Detector, the Zebra presents the timing surface); what is new is the recipe that binds them as a window-by-window fly-collection.

- **The catalog has no Method that fits, so i24 earns a Capability.** The tomography Methods bind RotaryStage + Camera + Scintillator over a rotation trajectory, and the I03 rotation MX Methods are a continuous omega sweep over a single crystal; neither matches a triggered raster over a grid of static samples. So serial crystallography is a new `serial_crystallography` Capability rather than a Method under an existing one. Whether it enters CORA's catalog is an owner decision, so the Practice renders pending (SSX-1). i24 is the first synchrotron consumer; the SLAC LCLS-MFX XFEL deployment already carries the same Method pending, so the second consumer is the graduation watch-item.

- **The chip raster is hardware-sequenced, and that sequencing is the seam CORA's edge replaces.** The serial trajectory (set a window, gate the exposure, step to the next) runs on the PMAC motion controller, with the Zebra FPGA TTL-gating the detector and the fast sample shutter per window off encoder position-compare. CORA does not model the PMAC motion program or the Zebra trigger graph as devices; it drives them through EPICS as the orchestration the edge conducts. The detailed raster pattern, the per-window dwell, and the trigger timing are calibration the deployment must supply (SSX-1).

- **The fixed-target chip is a Fixture and a Subject grid, not a PV.** The chip itself is the addressable holder the stage rasters one window at a time, and the crystals it carries are Subjects. The chip stage is a `LinearStage` Asset, but the grid geometry and the well / aperture map live in beamline software, not on a PV, so the chip-as-Fixture and the Subject grid are deferred as a CORA modelling decision (CHIP-1). Whether the chip windows are Subjects in a custody grid is the load-bearing question for the serial Subject thread.

- **There is no sample-exchange loop to model.** Rotation MX at I03 leans on an autonomous robot that loads pins one crystal at a time, which becomes a Procedure plus a Subject custody thread. i24 has no robot and no per-crystal exchange: one chip carries thousands of crystals, loaded once and rastered as a unit. The custody thread is over the chip and its grid, not over a stream of mounted pins.

The concrete recipe (the raster pattern, the per-window dwell, the laser and Zebra trigger timing, the chip grid map) is calibration the deployment must supply. See [Open questions](#open-questions) for what must be confirmed first.

## Governance

*Who would act at i24, and the trust shape that would gate it. Design-phase.*

Governance at i24 follows the same model as the CORA pilots: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

i24 is a further beamline at the Diamond Site, so it reuses the Diamond facility envelope rather than creating a new one: the Diamond operator pool, the safety review structure, and the safety forms are facility-wide and inherited. i24 adds only its own beamline-bound principals, carried pending on the [Diamond Site page](../diamond/index.md). The operator pool and safety-review structure are site-level and shared across the beamlines, so they are not yet instantiated per beamline (GOV-1). This is the same reuse pattern 7-BM follows at APS, the opposite of the new-Site work I22 did.

Because i24 is a modelling exercise, the concrete trust shape is not instantiated. What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the Diamond Site, not on the beamline, and the beamline links up to them. The Diamond PSS clearance is carried pending because its form names are not confirmed.

The safety tier behind the beam is the personnel safety system. The hutch photon shutter is dodal's interlocked hutch shutter, which sits behind a PSS interlock; the search-and-secure permit signals are the leaves that must be satisfied before the beam can enter the enclosure. CORA reads the shutter as a `Shutter` Asset, but the PSS permit leaves are not named in the descriptor and are not invented here, so the Enclosure permit signals are carried pending (PSS-1).

One hazard is sharper at i24 than at the rotation-MX siblings. The fixed-target serial collection rasters an addressable chip of thousands of static crystals across the chip stage, and the PMAC motion controller fires lasers on encoder edges during the raster. Whether those lasers are an excitation source CORA should model as a device or only a trigger setting with a Clearance hazard is deferred (LASER-1). If they are a hazard, the laser interlock would be gated by a Clearance issued after a separate safety review, the same shape the other deployments reserve for unattended or hazardous operation. None of that is built yet; the seam is reserved, not invented. Unlike the rotation-MX siblings, i24 has no sample-changing robot, so there is no autonomous-loading Clearance to model here.

The off-roadmap question of whether Diamond becomes a real CORA Site is unanswered. The concrete Zone, Conduit, and Policy instances, the operator pool, and any laser Clearance would land if the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's i24 content lives, why this first serial-crystallography deployment coins no new vocabulary, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at i24 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes i24 new

i24 is CORA's first serial / fixed-target crystallography. Unlike I03 rotation MX (one crystal, a continuous omega sweep), i24 raster-scans a fixed-target chip holding thousands of static crystals, taking one diffraction snapshot per addressable window, hardware-sequenced on the PMAC motion controller with Zebra TTL gating and no goniometer rotation. The novelty is the acquisition shape, a triggered chip-raster fly-collection over a sample grid, which is a new Capability deferred as a question (SSX-1). It forces no new device Family.

### No new families

i24 introduces no new device class. Every device reuses an existing catalog or loose Family, which is the strongest possible outcome for the families-only descriptor mode:

- The vertical pin goniometer reuses the catalog `Goniometer`, the Family I03 graduated.
- The fixed-target chip stage (dodal's PMAC, an XYZ stage) reuses `LinearStage`. The serial raster trajectory, the encoder position-compare, and the laser triggers run on the PMAC controller; they are the orchestration seam CORA's edge replaces, not a device Family.
- The Eiger and Jungfrau detectors reuse `Camera` (Detector Role); the on-axis viewer reuses `Camera`; the Zebra reuses `TimingController`; the DCM reuses `Monochromator`; the focusing mirrors reuse `Mirror`; the attenuator reuses `Filter` (the I03 / i15-1 precedent, not a new Attenuator kind); the aperture, beamstop, and detector / chip stages reuse `Aperture` / `BeamStop` / `LinearStage`; the shutters reuse `Shutter`.
- The dual backlight binds the catalog `Backlight` Family (graduated across the MX / imaging fleet); the machine source state reuses the loose `StorageRing`. No new loose family either.

### Deliberately not here yet

- **The fixed-target chip as a Fixture / Subject grid (`CHIP-1`).** The chip is a holder of thousands of static crystals that the stage rasters one window at a time. The chip stage is a `LinearStage` Asset; the chip itself (the addressable grid, the well / aperture map) is a Fixture, and the crystals are Subjects, a CORA modelling decision. The grid map lives in beamline software, not a PV, so it is carried as the open `CHIP-1` rather than modelled now. Whether the chip windows are Subjects in a custody grid is the load-bearing question for the serial Subject thread.

- **The serial-crystallography Capability (`SSX-1`).** The chip-raster fly-collection (set a window, gate the exposure, step to the next) is a new acquisition Capability. Whether it enters CORA's catalog as a Method is an owner decision; the Practice renders unlinked, pending. i24 is the first synchrotron consumer; the SLAC LCLS-MFX XFEL deployment carries the same Method pending, so the second consumer is the graduation watch-item.

- **The PMAC laser triggers (`LASER-1`).** The PMAC fires lasers via M-variables on rising / falling encoder edges. Whether these are a pump-probe excitation source CORA should model as a device, or only a trigger setting and a Clearance hazard, is deferred.

- **The collection-Assembly question.** Whether the goniometer, chip stage, and detector compose an Assembly is deferred, as the other Diamond deployments deferred their Assemblies in descriptor mode; the first cut is flat Assets.

- **The simulated devices and full asset-tree scenarios.** No `test_i24_*.py` registers the i24 asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the i24 team to confirm before the model can be trusted.*

i24 was reverse-engineered from Diamond's open controls library ([dodal](https://github.com/DiamondLightSource/dodal), `src/dodal/beamlines/i24.py` and its device classes), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from the source rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The i24 insertion-device source (gap, type), which dodal does not expose as a device here. | An undulator source; only the Synchrotron machine state is read. | The source Asset detail. |
| ENC-1 | Blocks-go-live | Is i24 one optics hutch plus one experiment hutch, or a different enclosure split? | Two enclosures: i24-optics and i24-experiment. | The Enclosure grouping. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The machine source state i24 reads (ring current, top-up, mode) and its PVs. | Observe-only via dodal's Synchrotron device, a loose `StorageRing`. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The DCM crystal cut, d-spacing, and incident-energy range. | A double-crystal monochromator on `BL24I-MO-DCM-01:`; values pending. | The monochromator Asset. |
| OPT-1 | Nice-to-have | The focusing-mirror coatings and the selectable focus modes. | Focusing mirrors bound to `Mirror` (dodal FocusMirrorsMode); modes pending. | The mirror Asset detail. |
| ATTN-1 | Nice-to-have | The attenuator filter set and transmission levels. | A filter-based attenuator bound to `Filter`, not a new kind (the I03 / i15-1 precedent). | The attenuator Asset. |
| OPT-2 | Nice-to-have | The aperture, beamstop, and detector-stage axis roles. | Beam-defining aperture / positioned beamstop / detector translation; axes pending. | The optic Asset detail. |

### Sample and serial collection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | The vertical goniometer circle and pin-translation axes. | A vertical pin goniometer bound to the catalog `Goniometer`; axes pending. | The goniometer Asset. |
| CHIP-1 | Blocks-build | How is the fixed-target chip addressed: the grid geometry, the well / aperture layout, and how a collection window maps to a stage position? | An addressable chip on the XYZ chip stage; the grid map lives in beamline software, not a PV. | The chip addressing; the CORA Fixture / Subject-grid modelling is on [Model](#deliberately-not-here-yet). |
| SSX-1 | Blocks-go-live | The serial-collection sequence: the raster pattern, the per-window dwell, and the laser / Zebra trigger timing. Does serial crystallography enter CORA's catalog as a Capability? | A triggered chip-raster fly-collection; the Capability is deferred, the Practice rendered pending. | The serial-collection shape; the CORA Capability is on [Model](#deliberately-not-here-yet). |
| LASER-1 | Nice-to-have | The PMAC-controlled lasers: are they a pump-probe excitation source CORA should model, or only a trigger setting and a hazard? | Carried as a trigger setting on the chip-collection seam, not a device; modelling deferred. | The laser model or hazard treatment. |
| BACKLIGHT-1 | Nice-to-have | The dual backlight PV root and its positions. | Binds the catalog `Backlight` Family; the root `BL24I` and positions pending. | The backlight Asset. |

### Detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector configuration: the Eiger as the production detector, the Jungfrau as commissioning, and the beam-centre. | Eiger is the primary `Camera` (Detector Role); Jungfrau carried as commissioning. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from dodal current and correct? | The handles in the descriptor are taken from dodal and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals behind the interlocked hutch shutter. | The hutch shutter is dodal's InterlockedHutchShutter; the permit leaves are to be named, not invented here. | The Enclosure permit signals. |
| SUP-1 | Nice-to-have | The vacuum extent and the facility supplies a run draws on. | Photon beam, cooling water, and vacuum on the optics path. | The Supply observations. |
| GOV-1 | Nice-to-have | The Diamond operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the Diamond Site, not instantiated per beamline. | The governance principals. |
