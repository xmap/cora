# Notes

## Techniques

*What the modelled part of 32-ID is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. This scaffold models 32-ID's TXM endstation, so the techniques below are the TXM ones, carried as design intent. The function view survives the eventual hardware choices, which is why it can be written before the optics are confirmed.

### TXM nano-tomography

The transmission X-ray microscope images the internal structure of a sample at nanometre-class resolution by magnifying the transmitted beam through a Fresnel zone plate, then rotating the sample for a tomographic reconstruction.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Nano-tomography | `tomography` | step-scan projections over a rotation, magnified by the zone-plate optics |
| Zernike phase-contrast nano-tomography | `tomography` | the phase ring is inserted for phase contrast; a Plan setting over the same Method, not a separate Method |

Both realize `cora.capability.tomography` and need the [TXM sample stage](sample.md) and the [TXM detector](detector.md). Phase contrast is a configuration of the same tomography Method (the phase ring inserted), mirroring the 2-BM decision that laminography is a tomography Plan at a tilt setpoint rather than a new Method.

### Energy and beam mode

32-ID delivers white or monochromatic beam, selected by the P4-50 mode shutter. The monochromatic branch uses the Si(111) monochromator over a 7 to 40 keV range. Whether CORA models the white-to-mono switch as a new Capability or as an extension of the existing `energy_change` vocabulary is an open design decision recorded on [Model](#model); the world-fact half (the switch structure) is `MODE-1` on [Open questions](#open-questions).

### Not modelled yet

32-ID's other techniques run on instruments this scaffold defers (see [Model](#deliberately-not-here-yet)): white-beam high-speed imaging and ultrafast diffraction (32-ID-B), in-situ additive-manufacturing imaging (32-ID-B), and projection microscopy. Their Methods join when those instruments are modelled.

The concrete acquisition recipes (scan sequences, energies, exposure) are not written yet; they join as the deployment approaches the point where CORA drives 32-ID. See [Open questions](#open-questions) for what must be confirmed first.

## Governance

*Who will act at 32-ID, and the trust shape that will gate it. Design-phase.*

Governance at 32-ID follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

32-ID is a design-phase scaffold in CORA, so this shape is not yet instantiated. The 32-ID operator pool and beamline-scientist assignments are not modelled ahead of confirmation; CORA does not invent a 32-ID operator roster.

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [APS Site](../aps/index.md#safety-and-governance), not on the beamline, and the beamline links up to them rather than restating them. 32-ID adds hazard classes beyond the 2-BM tomography envelope, a class-4 laser on the additive-manufacturing rig, pressurized helium and cryogens, that an experiment Clearance would carry; those land with the instruments that bring them, which are deferred (see [Model](#deliberately-not-here-yet)).

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives 32-ID, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's 32-ID content lives, a TXM nano-tomography beamline whose optic classes graduated once FXI shared them, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 32-ID |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Deliberately not here yet

These are the parts of 32-ID this scaffold leaves out on purpose. Each is a CORA scope decision, not a fact the beamline team needs to supply, so it lives here rather than on [Open questions](#open-questions).

- **The canted branch structure.** The descriptor models one root Unit Asset and one optics train. Whether 32-ID becomes two root Assets (per branch) is held until `TOPO-1` resolves the canted geometry. The root identity and `facility_code` binding do not migrate when it does: a one-to-two split adds Component sub-trees, it does not re-home the root.

- **The white-to-mono beam-mode vocabulary.** Whether the mode switch is a new Capability or an extension of the existing `energy_change` Capability is decided when the mode is modelled, not now. The world-fact half (the switch structure and sequence) is `MODE-1`; the vocabulary half is this decision.

- **High-speed imaging and ultrafast diffraction (32-ID-B).** White-beam high-speed imaging reuses the imaging spine, but ultrafast white-beam diffraction (HSID) produces diffraction patterns, which have no precedent in CORA's all-imaging catalog. Whether diffraction is in CORA's scope is an owner decision; until it is made, neither instrument is modelled and no diffraction Capability is coined.

- **The additive-manufacturing laser rig (32-ID-B).** The powder-bed-fusion rig is a user-brought, actuated, non-X-ray energy source with no Family or Role precedent. The default is to model the class-4 laser as a `Clearance` hazard on an experiment, not as an Asset CORA drives. Whether CORA ever orchestrates the laser is an owner decision.

- **The projection microscope (PM).** The source docs for the PM are still "space holder", and its most distinctive parts (a helium-atmosphere KB system, a robotic sample-exchange arm) are the least documented. Modelling it now would be invention. The robotic sample changer in particular would force a sample-changer shape CORA does not have; it waits until the PM is documented and a real device list exists.

- **Integration scenarios and vendor Models.** No `test_32id_*.py` registers 32-ID Assets, and no vendor Models are bound. Scenario code is where Assets become real, and hard-registering a design-phase, pre-APS-U-mixed beamline would commit speculative structure. Both land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the 32-ID team to confirm before the model can be trusted.*

32-ID is a design-phase scaffold built from the published [32-ID docs](https://github.com/decarlof/32id-docs), which mix pre-APS-U and current values, so almost every value on the [device pages](index.md) is carried as a fact still to confirm. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are recorded on [Model](#deliberately-not-here-yet) instead). It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed, with the reason in the commit. Priorities are `Blocks-build` (the answer changes the structure of the model, so CORA cannot finalize the shape without it), `Blocks-go-live` (a placeholder is fine for the description, but the real value is needed before CORA observes or drives the hardware), and `Nice-to-have`.

### Topology and scope

The one structural unknown: how the canted source and its branches map onto CORA's Asset model. The answer decides whether 32-ID is one root Asset or two.

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | 32-ID is canted: two undulators feeding two branches. Do `32-ID-B` and `32-ID-C` run off separate beams (two canted branches), and does the `32-ID-A` optics set (mask, slits, monochromator, mode shutter) serve both branches or is it duplicated per branch? Which undulator feeds which branch? | One root Unit Asset `32-ID` with one optics train; the branch multiplicity is unmodelled pending this answer. | One-vs-two root Assets and one-vs-two beam walks in the [descriptor](index.md). |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | What are the EPICS PV handles (and drive crates / IOC hosts) for each modelled device? | Control handles are unassigned; CORA leaves each device handle empty. | Wiring each Asset to a real control handle. |
| PSS-1 | Blocks-go-live | What are the PSS search-and-secure permit signals for the three hutches (`32-ID-A`, `-B`, `-C`)? | Three hutches exist with permit signals to be named. | The Enclosure permit signals. |
| BLEPS-1 | Nice-to-have | Are the BLEPS (equipment-protection) fault and status signals readable as PVs for an external observer, and which map to a utility versus a specific device? CORA observes outcomes only; it never models the interlock logic. | Utility faults map to Supply status, device faults to an Asset condition; the matrix is not modelled. | The Supply and Asset condition mapping. |

### Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The exact device types and parameters of the two canted undulators (the source table lists "Planar 1.35" downstream and "Planar 2.8" upstream; a "U33" tuning curve is published). How do these labels relate, and what are the periods and gaps? | Two `InsertionDevice` Assets, downstream and upstream, planar; periods and the U33 relationship unconfirmed. | The insertion-device specs. |
| SRC-2 | Nice-to-have | The fixed front-end mask aperture and position, and the front-end window stack (count, material, thickness). | A beam-defining `Mask` near 24 m and a `Window` (Be assumed); sizes unconfirmed. | The front-end mask and window specs. |
| MONO-1 | Blocks-go-live | The Si(111) monochromator detail: per-axis motors, energy range over the 7 to 40 keV span, and whether it drives from a saved per-energy table. | One `Monochromator` Asset, Si(111), 7 to 40 keV; axes and saved positions unconfirmed. | The monochromator axes and energy model. |
| MODE-1 | Blocks-build | The white-beam to monochromatic switch (the P4-50 mode shutter with its white-beam stop and combined mono stops). Is this a per-branch hard split (one branch always white, one always mono) or a switchable mode on one optics set, and what is the switching sequence and interlock? | A `ModeShutter` plus beam stops; switching is a coordinated, interlocked move, structure tied to TOPO-1. | The beam-mode model (and whether it is a new Capability or an `energy_change` extension, decided on [Model](#model)). |
| LAYOUT-1 | Nice-to-have | A single z-coordinate reference for the layout. The published docs give per-hutch positions but no common origin. | z values are carried as approximate from-source and flagged confirm. | Exact device z positions. |

### TXM endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TXM-1 | Blocks-go-live | Is the published TXM component list current post-APS-U, or does it carry pre-APS-U hardware? Specifically the granite stages, the rotation stage (Aerotech assumed), and the sample-positioning stack (Kohzu assumed). | The published overview is taken as current; stage models and axes carried confirm. | The TXM stage Assets and models. |
| OPTICS-1 | Blocks-go-live | What is the beam-condensing optic upstream of the sample: a capillary condenser, a condenser zone plate, or KB optics? | One `Condenser` Asset bound to the catalog Family; optical type unconfirmed. | The condenser optic identity. |
| OPTICS-2 | Blocks-go-live | The objective Fresnel zone plate parameters (outermost-zone width, diameter, material) that set the TXM resolution. | One `ZonePlate` Asset bound to the catalog Family; parameters unconfirmed. | The zone-plate spec. |
| OPTICS-3 | Nice-to-have | The Zernike phase ring used for phase contrast: its parameters and whether it is inserted or retracted per scan. | One `PhaseRing` Asset bound to the catalog Family; inserted/retracted state not modelled. | The phase-ring spec and state model. |

### Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The TXM detector camera model, sensor, and frame rate. | One `Camera` Asset; model and sensor unconfirmed. | The camera Model binding. |
| DET-2 | Nice-to-have | The TXM indirect-detection objective magnification set and the scintillator material and thickness. | An `Objective` and a `Scintillator` Asset; details unconfirmed. | The detector optics specs. |

### Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | Nice-to-have | Is the TXM flight path helium-filled or evacuated, and what gas supplies does the endstation draw on? | A flight path exists; its gas is unconfirmed (the projection microscope uses helium, the TXM is unconfirmed). | The Supply records and flight-path model. |
