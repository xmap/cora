# Notes

## Techniques

*What CORA would run at I20-1: energy-dispersive EXAFS, a [Catalog](../../catalog/methods.md) Method bound through a [Diamond Practice](../diamond/index.md). It is the dispersive complement to the scanning-XAS axis, and its Capability is deferred, the more so because the dispersive devices are not yet in source.*

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Energy-dispersive EXAFS (EDE) | `energy_dispersive_exafs` | the whole absorption spectrum read in one shot off a polychromatic fan on a strip detector; time-resolved. New Capability, pending (TECH-1); the dispersive polychromator + strip detector are not yet in source (POLY-1 / STRIP-1) |
| Fluorescence-yield EXAFS | `energy_dispersive_exafs` | the same dispersive acquisition read in fluorescence on the Xspress3, a secondary mode (DET-1) |

The technique is recorded as a pending [Practice](../diamond/index.md) on the Diamond Site.

### Why the Capability is deferred (and the heart is an open question)

EDE is a new science Capability for CORA: scanning XAS (NSLS-II BMM) steps a monochromator through an edge and the per-energy readings are the data, while EDE reads every energy at once off a dispersed fan. CORA carries the EDE Method as pending, the dispersive complement to the energy-scan question BMM opened (TECH-1 / the ENERGY-1 cohort), rather than coining it, the same earn-the-abstraction discipline every new-domain technique follows.

The sharper point at I20-1 is that the two devices the Capability turns on, the bent-crystal polychromator and the position-sensitive strip detector, are not in the public dodal commissioning module. So this is a partial first cut: the technique is named and its periphery modelled (the energy-selecting turbo slit, the fly-scan PMAC and PandA timing, the fluorescence Xspress3), but the dispersive optic and detector are explicit open questions (POLY-1, STRIP-1). The polychromator in particular would be a genuinely new optic class, an energy-fanning bent crystal distinct from a `Monochromator`, that CORA would weigh as a Family once it is PV-bound; coining it now, with no source PV, would be invention.

The spectrum extraction (turning the dispersed strip frame into an absorption spectrum) is `ComputePort` work, not a beamline Method.

## Governance

*Who may act at I20-1 and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [Diamond Site](../diamond/index.md); on the beamline they surface through the actions they take. The human roster is not in the dodal module (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the Diamond Site. An I20-1 beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may arm the detector, drive the turbo-slit fly-scan, change the energy selection, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The Diamond proposal and cycle are a fact CORA's Campaign uses for custody.

### Time-resolved collection

EDE's reason for existing is speed: a full absorption spectrum in sub-second time, so a reaction can be followed as it runs. That makes the unattended, repeated, fast acquisition the place CORA's custody and trust shapes earn their keep, the engine holds the fly-scan and the detector arming while the trust boundary bounds what may change mid-series. If an autonomous Agent were added to trigger collections on a sample-environment cue or decide when a kinetic series is complete, it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet; with the dispersive detector still an open question (STRIP-1), this stays design intent.

## Model

*The developer's by-kind index: where each CORA aggregate's I20-1 content lives. It hosts no content of its own. Design-phase scaffold, deliberately partial.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at I20-1 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (I20-1-OH optics, I20-1-EH experiment) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), and a deliberately partial one: the dodal commissioning module is thin. Left out on purpose:

- **The dispersive heart of EDE.** The bent-crystal polychromator (POLY-1) and the position-sensitive strip detector (STRIP-1), the two devices that make the technique energy-dispersive, are not in the public source, so they are named open questions, not modelled. The polychromator would be a genuinely new optic class (an energy-fanning bent crystal, distinct from `Monochromator` / `GratingMonochromator`); CORA would weigh a `Polychromator` Family once it is PV-bound, not before. Coining it from no source PV would be invention.
- **No new Family, no loose family.** What is modelled reuses existing families only: the turbo slit binds `Slit`, the PMAC `MotionController`, the PandA `TimingController`, the sample stage the graduated `Manipulator`, the Xspress3 the graduated `EnergyDispersiveSpectrometer`.
- **The mock / skip honesty.** The sample stage is a dodal `mock` (real PVs, motors being reconnected, STAGE-1); the Xspress3 is a dodal `skip` (defined, not loaded by default, DET-1). Both are carried `confirm` and flagged, not asserted live.
- **The absent source / optics / diagnostics chain.** No source, front-end, primary mirror, attenuator, ion chamber, flux monitor, or beam-position monitor is in the commissioning module; the source is carried PV-less (SRC-1) and the rest are open questions.
- **No new Capability or Method.** Energy-dispersive EXAFS is a pending Practice on the Site (the dispersive complement to the BMM energy-scan question, TECH-1); MX3-style, the technique is reinforced-and-deferred, not coined.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive, and whose primary detector is not even in source, would be invention; they land when the dispersive devices are PV-bound and the team confirms.

## Open questions

*What CORA needs the I20-1 team to confirm. This model is reverse-engineered from the public dodal controls library (`src/dodal/beamlines/p51.py`, the i20-1 commissioning module): the EPICS PVs are read from it, but it is a thin commissioning roster and the dispersive heart of EDE is not in it. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### The dispersive heart (absent from source)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| POLY-1 | Blocks-build | The bent-crystal polychromator that fans the energy band across the sample, the defining EDE optic. It is not in the dodal module (only the turbo slit at the polychromator enclosure `BL51P-OP-PCHRO-01` is). What are its PVs and axes (crystal bend, Bragg, position)? It is a genuinely new optic class (an energy-dispersing bent crystal, distinct from a Monochromator); CORA would weigh a new `Polychromator` Family once it is PV-bound. | Not modelled; named here, no Family coined without a source PV. | The polychromator Asset and a possible new Family. |
| STRIP-1 | Blocks-build | The position-sensitive strip detector that reads the dispersed absorption spectrum in one shot, the EDE primary detector (e.g. an XH / germanium microstrip). It is not in the dodal module. What is its PV, and does it fit `Camera` (a 1D frame) or warrant a new detector class? | Not modelled; named here, no device coined without a source PV. | The strip-detector Asset and its family. |

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The insertion-device source, front-end, and primary mirror: none is in the commissioning module. The PV root `BL51P` would carry them. | An insertion-device source, identity-only, no PV. | The Source and front-optics Assets. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs (not in the dodal module). | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | The hutch layout and names (the dodal module exposes no enclosure structure). | An optics hutch plus an experiment hutch. | The Enclosure set and roles. |

### Sample, detector, controls

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The sample alignment stage axis set and reconnection: the dodal module constructs `alignment_x` / `alignment_y` (`BL51P-MO-STAGE-01:X` / `Y`) as a mock, noting the motors are being reconnected on the beamline. | A `Manipulator` Asset (X / Y); the PVs are real but not yet connected. | The SampleStage axes and live PVs. |
| DET-1 | Nice-to-have | The Xspress3 fluorescence detector (`BL51P-EA-DET-03:`, 16-channel) is defined but constructed with `skip=True` in dodal (not loaded by default). Is it live, and what is the I0 / It / ion-chamber flux chain (none is in the module)? | One `EnergyDispersiveSpectrometer` Asset; flux chain blank. | The detector roster and flux monitors. |
| DRIVE-1 | Blocks-go-live | The PMAC trajectory controller (`BL51P-MO-STEP-06:`) and PandA box (`BL51P-EA-PANDA-01/02:`) firmware / IPs. | Families bound (MotionController, TimingController), specifics blank. | The controller Models. |
| TECH-1 | Blocks-go-live | Does the energy-dispersive-EXAFS Capability enter CORA's catalog, or stay deferred? It is the dispersive complement to the scanning-XAS / energy-scan question (the BMM ENERGY-1 cohort). | The EDE Method is a pending Practice, not yet in the catalog. | The EDE Capability scope. |
