# Notes

## Techniques

*What the modelled part of i19 is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md#the-techniques-adapted-here) is how a facility adapts it. i19 is CORA's first *chemical* crystallography beamline: small-molecule single-crystal structure solution, distinct from the macromolecular MX (I03, I24, FMX, MX3) the rest of the fleet carries. The function view below is written before the Method is coined, because it survives the eventual catalog vocabulary choice.

### Single-crystal diffraction

The Newport kappa four-circle goniometer orients a single crystal in the monochromatic or variable-wavelength beam, sweeps reciprocal space, and the Eiger records the scattered intensity as a function of momentum transfer. This is the same diffraction function the magnetic single-crystal stations already do; what differs at i19 is the science the data feed, not the recipe.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Single-crystal diffraction | `diffraction` | reciprocal-space scans on the kappa four-circle with the Eiger; shares the 4-ID / 8-ID / CSX `diffraction` Method, pending (TECH-1) |
| Variable-wavelength diffraction | `diffraction` | the same Method over a coordinated energy move; a Plan / settings difference, not a new Method (TECH-1) |

This needs the [diffractometer](sample.md) (the kappa four-circle, plus the 2-theta detector arm and det_z), the [Eiger detector](sample.md), and the shared-optics energy control. A few points of intent shape how the Method binds here:

- **Single-crystal diffraction reuses the pending `diffraction` Method.** The prior consumers are the magnetic single-crystal stations (4-ID, 8-ID, CSX); i19 is a fourth consumer of the same recipe. The Method binds a Goniometer that orients the crystal and a Camera that captures the diffracted frames. Chemical crystallography (small-molecule structure solution) versus the magnetic single-crystal science at 4-ID is a **Practice-level** difference, not a Method-level one: the I19_diffraction_practice (pending) is where the chemical adaptation lives, over the portable diffraction Method (TECH-1).
- **The kappa four-circle is plain Goniometer reuse.** kappa is a setting per the catalog Goniometer note, so the four-circle does not earn a new Family. The larger four-circle (phi / omega / kappa, the 2-theta arm, det_z, sample-centring) is the named-not-built `Assembly(Diffractometer)` composed over that Goniometer (DIFF-1). The reciprocal-space coordination binds `PseudoAxis` (DIFF-2).

### Serial / microfocus fixed-target delivery

i19 carries a serial / microfocus fixed-target arm: a second sample stage (x / y / z / phi) that presents many crystals to a microfocused beam on a fixed target. This is a **delivery sub-mode** of single-crystal diffraction, not a separate technique. It binds the same `diffraction` Method, with the second stage modelled as a second Goniometer (SERIAL-1).

| Delivery | Catalog method | Notes |
| --- | --- | --- |
| Fixed-target serial collection | `diffraction` | many crystals on the serial stage; the same Method, a delivery sub-mode (SERIAL-1) |

The one part that reaches past the present catalog is the **raster**: stepping the fixed target through a grid of positions and collecting at each would touch a grid-scan-style Method the catalog does not yet carry. Until that Method exists, the raster is carried as a note on the serial sub-mode, not modelled as its own recipe (SERIAL-1). The microfocused beam is shaped by the [MAPT pinhole and collimator](sample.md), whose aperture sizes are a Capability settings schema (the i03 MAPT precedent) (APERTURE-1).

### Not modelled yet

The concrete acquisition recipes are deferred: oscillation and scan ranges, exposures, the variable-wavelength sequence, and the serial raster pattern are calibration the deployment must supply, and writing them now for an unmodelled beamline would be invention, not record. They join as the deployment approaches the point where CORA drives i19.

Whether the `diffraction` Method (and the grid-scan-style Method the raster would need) enters CORA's catalog at all is an owner-scope decision, recorded on [Model](#model); the raster's catalog gap is SERIAL-1 and the Method-coin question is TECH-1. See [Open questions](#open-questions) for the world-facts to confirm first, including which hutch holds the four-circle (ENC-1).

## Governance

*Who would act at i19 and the trust shape that would gate it. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority. Not yet instantiated (scaffold).*

Governance at i19 follows the same model as the other Diamond beamlines: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape: a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what. The human roster is not in the dodal module (GOV-1), so the principals below are the design shape, not a registered list.

Because i19 is a scaffold, the concrete trust shape is not instantiated. What is already settled is the boundary: clearances (the safety state that must be active to start) are issued at the Diamond Site, not on the beamline, and the beamline links up to them.

### Who acts

The Diamond operator pool runs an i19 beamtime, with a beamline scientist and a safety reviewer in the facility-wide review chain. These are the Diamond facility principals, carried pending at the [Diamond Site page](../diamond/index.md#safety-and-governance); i19 inherits them rather than coining its own (GOV-1). The Diamond proposal and cycle are a fact CORA's Campaign uses for custody.

### The trust boundary

i19's boundary is shaped by the Trust BC aggregates (Zone, Conduit, Policy); the [Trust module](../../architecture/modules/trust/index.md) defines what each one is. This page records only the intended i19 instances, all pending until the beamline approaches real scope.

| Zone | Conduit | Endpoints |
| --- | --- | --- |
| `i19 Zone` | `i19 Local Conduit` | `i19 Zone` -> `i19 Zone` |

A Policy governs who may issue which command across a Conduit.

| Policy | Permitted principals | Permitted commands |
| --- | --- | --- |
| `i19 Operations Policy` | Diamond operator pool (GOV-1) | Operator-driven commands (Equipment, Recipe, Operation, Run, Subject, Dataset, Caution, Clearance, Supply, Campaign) |
| `i19 Agent Policy` | Diamond agent principals (GOV-1) | Decision family: `RegisterDecision`, `RateDecision`, `AppendInferences` |

### The safety envelope

i19 inherits the Diamond [safety envelope](../diamond/index.md#safety-and-governance). The one safety signal CORA can name today is the dodal interlocked optics shutter (`OpticsShutter`, BL19I-PS-SHTR-01), which is PSS-interlocked and bound to the Shutter family. Beyond that, the PSS search-and-secure permit signals per hutch are pending and are not invented (PSS-1). Clearances are issued at the Diamond Site and the beamline links up to them.

### The active-hutch permit (ACCESS-1)

i19 has two experiment hutches in series, EH1 (`i19-1`) and EH2 (`i19-2`), that share one optics line (`i19-optics`, the shared BL19I optics). This is the i19-specific governance element, and it is the genuine novelty of the deployment: only the **active** hutch may drive the shared optics. A non-active hutch may still observe the shared optics state, but it may not move them.

dodal expresses this with a central arbiter, the i19-blueapi optics service. A hutch reads the shared-optics state directly over EPICS, but its writes (change the energy, operate the experiment shutter, move the attenuator, set a mirror piezo) are posted to the arbiter. The arbiter compares the requesting hutch against the active-hutch readback (BL19I-OP-STAT-01:EHStatus) and runs or rejects.

CORA models this as an **Enclosure-permit plus Trust-gate** over the shared-optics Assets, not as a device family (ACCESS-1):

- The Enclosure-permit is the active-hutch state itself: of the two Enclosures `i19-1` and `i19-2`, the one currently holding the permit is the only one whose commands against the shared `i19-optics` Assets may proceed (ENC-1).
- The Trust-gate is the Policy condition layered on the shared-optics commands: a command to change energy (`BeamEnergy`, the coordinated DCM plus undulator plus mirror-stripe move, MONO-1), operate the optics shutter (PSS-1), move the attenuator (`Attenuator`, the i03 precedent, ATTN-1), or set a focusing-mirror piezo (`HorizontalFocusingMirror` / `VerticalFocusingMirror`, with its hutch-keyed coating stripe Si 5-10 / Rh 10-20 / Pt 20-30 keV, OPT-1) is admitted only from the hutch that holds the permit.
- The i19-blueapi arbiter is the **actuate-floor seam** partner, the same "EPICS is the floor" pattern the rest of the Diamond fleet follows, here a blueapi-arbiter floor. CORA's gate decides whether the command is authorized; the arbiter remains the floor that compares the requesting hutch against the active-hutch readback and runs or rejects against EPICS.

The shared-optics devices are single Assets, access-gated rather than duplicated per hutch: the monochromator (DCM, MONO-1), the two focusing mirrors (OPT-1), the attenuator (ATTN-1), the coordinated `BeamEnergy` pseudo-axis (MONO-1), and the optics shutter (PSS-1) all live in `i19-optics` and are reached through the permit. The undulator (`Undulator`, SR19I-MO-SERVC-01) is coordinated with the DCM on an energy move (SRC-1); the storage ring is observe-only machine state (MACHINE-1).

None of this is instantiated yet. The Zone, Conduit, and Policy instances, the Diamond operator pool, and the active-hutch permit gate would land if the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's i19 content lives, why the four-circle is not the novelty and the dual-hutch access-control seam is, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at i19 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the incident-energy PseudoAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes i19 new (and what does not)

i19 is CORA's first chemical (small-molecule) single-crystal crystallography beamline. The fleet's other diffraction-imaging crystallography is all macromolecular MX (I03, I24, FMX, MX3); i19 solves small-molecule structures on a Newport kappa four-circle goniometer with an Eiger detector, plus a serial / microfocus fixed-target arm.

The honest framing: the instrument is **not** the novelty. The kappa four-circle is plain catalog `Goniometer` reuse:

- The catalog `Goniometer` note states that **chi-versus-kappa and axis-count are a per-Asset setting, not a Family split**. So the phi / omega / kappa sample circles bind the catalog `Goniometer`, exactly as the i03 Smargon and the MX3 mini-kappa do.
- The larger four-circle (the goniometer plus the 2theta detector arm plus a reciprocal-space axis) composes the catalog `Assembly(Diffractometer)`, the 8-ID / 4-ID / i06-1 pattern, named-not-built in descriptor mode (`DIFF-1`, `DIFF-2`).
- The single-crystal diffraction technique reuses the pending `diffraction` Method that 4-ID, 8-ID, and CSX already share; chemical-versus-magnetic single crystal is a Practice-level science difference, not a new Method (`TECH-1`).

What **is** genuinely new is the governance seam, below. i19 coins no new Family and changes nothing in the catalog.

### The dual-hutch access-control seam

i19 has two experiment hutches in series (EH1 and EH2) that share one optics line, and only the active hutch may drive the shared optics. dodal expresses this through a central arbiter (the i19-blueapi optics service): a hutch reads the shared-optics state directly over EPICS, but its writes (change energy, operate the experiment shutter, move the attenuator, set a mirror piezo) are posted to the arbiter, which compares the requesting hutch against the active-hutch readback (`BL19I-OP-STAT-01:EHStatus`) and runs or rejects the operation.

CORA models this without a new device family:

- **The shared-optics devices are single Assets** in the `i19-optics` enclosure (the `Monochromator`, `Undulator`, the two `Mirror`s, the `Filter` attenuator, the `Shutter`). A non-active hutch reading them read-only is the same Asset surfaced through a permit, not a second Asset.
- **The active-hutch permit is an Enclosure-permit + Trust-gate.** EH1 and EH2 are two `Enclosure`s; which one may drive the shared optics now is a permit axis on the Enclosure, governed by Trust authorization. The `BL19I-OP-STAT-01:EHStatus` readback is the read-model of that permit (`ACCESS-1`).
- **The i19-blueapi arbiter is an actuate-floor seam partner.** It is the same shape as the "EPICS is the floor" seam, here a blueapi-arbiter floor: today it performs the active-hutch arbitration; CORA's edge would conduct the run over its `ControlPort`, either driving through the arbiter or replacing its plan-orchestration per routine, a seam decision not pre-empted here.

This is the design-interesting content of i19: an Enclosure-permit-gated actuate seam, the first dual-hutch shared-optics arbitration in the fleet. The concrete Enclosure-permit, Trust, and seam instances are named, not built, in this scaffold.

### No new families

Beyond the four-circle (Goniometer) and the MAPT aperture (below), the rest reuse the catalog directly: the DCM binds `Monochromator`; the focusing mirrors bind `Mirror` (the coating stripe is a hutch-keyed setting); the attenuator binds `Filter` (the i03 precedent); the undulator binds `InsertionDevice`; the Eiger and the OAV viewing cameras bind `Camera`; the Zebra and PandA hardware triggers bind `TimingController`; the serial / microfocus arm binds a second `Goniometer`; the beamstops bind `BeamStop`; the shutter binds `Shutter`; the incident energy is a `PseudoAxis`. The machine state reuses the loose `StorageRing`.

- **The MAPT pinhole and collimator bind the catalog `Aperture` (`APERTURE-1`).** This follows the i03 ApertureScatterguard-at-MAPT precedent: the consumer-facing beam-defining Asset binds `Aperture`, composing the pinhole and collimator XY stages, with the configuration aperture sizes as a Capability settings schema. The discriminator tension (the catalog `Aperture` describes a fixed code pattern, while the MAPT is a driven, size-selectable opening) is carried as `APERTURE-1`; the i03 sibling, the same controls stack and the same MAPT, already binds `Aperture`, so i19 follows it.

- **The sample backlight binds the catalog `Backlight` Family.** i03, i24, and fmx already bind it; i19 is a further consumer of the illumination affordance now graduated across the MX / imaging fleet (`DET-1`). i19 adds a consumer, not a new Family.

### Deliberately not here yet

- **The Assembly(Diffractometer) and the reciprocal-space rule (`DIFF-1`, `DIFF-2`).** Named, not built, exactly as 4-ID, 8-ID, and i06-1 deferred theirs. The 2theta detector arm is a `RotaryStage` slot of the Assembly; det_z folds as a per-Asset axis on the arm (the i06-1 precedent).
- **The serial / microfocus raster (`SERIAL-1`).** The fixed-target arm binds a second `Goniometer`; the raster sub-mode (which would touch a grid-scan-style Method that the catalog does not yet carry) is carried as a note, not modelled.
- **The Enclosure-permit + Trust-gate + actuate seam instances (`ACCESS-1`).** The dual-hutch access-control is described above and is the governance novelty, but the concrete Zone / Conduit / Policy and the arbiter-seam drive-through-versus-replace decision are named, not built, in this scaffold.
- **The diffraction Method.** Whether single-crystal diffraction enters CORA's catalog as a Capability / Method is an owner decision; the Practice renders unlinked, pending, reusing the slug 4-ID / 8-ID / CSX share (`TECH-1`).
- **The centring image-recognition behaviour and the simulated devices.** The OAV pin-tip recognition is a Method behaviour on the Camera, not a device; no `test_i19_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the i19 team to confirm before the model can be trusted.*

i19 was reverse-engineered from the beamline's own bluesky device layer ([DiamondLightSource/dodal](https://github.com/DiamondLightSource/dodal): the `src/dodal/beamlines/i19*.py` factories and the `src/dodal/devices/` classes), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from dodal rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology, scope, and the dual-hutch seam

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The EH1 / EH2 grouping: which experiment hutch holds the four-circle and the Eiger, and which holds the on-axis viewing, and how the two hutches sit relative to the shared optics. | A shared `i19-optics` zone feeding two experiment hutches `i19-1` (EH1) and `i19-2` (EH2); the four-circle in EH2. | The Enclosure grouping. |
| ACCESS-1 | Blocks-go-live | The dual-hutch shared-optics access-control: only the active hutch may drive the shared optics, enforced by the i19-blueapi optics arbiter against the active-hutch readback (`BL19I-OP-STAT-01:EHStatus`). How should CORA represent the active-hutch permit and the arbiter? | An Enclosure-permit + Trust-gate over the shared-optics Assets, with the arbiter as an actuate-floor seam partner (the "EPICS is the floor" pattern). | The governance seam; the CORA modelling is on [Model](#the-dual-hutch-access-control-seam). |
| SRC-1 | Nice-to-have | The undulator period and type (`SR19I-MO-SERVC-01`). | An undulator coordinated with the DCM on an energy move; period pending. | The source Asset detail. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state i19 reads (current, fill). | Observe-only machine state, a loose `StorageRing`; the exact PVs pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The DCM crystal cut, the energy / wavelength range, and the energy partition rule (the variable-wavelength capability). | A double-crystal `Monochromator`; the energy is a `PseudoAxis` over the DCM and undulator; range pending. | The monochromator and incident-energy Assets. |
| OPT-1 | Nice-to-have | The focusing-mirror coatings and the stripe energy bands (Si / Rh / Pt), and whether the stripe is hutch-keyed. | Focusing mirrors bound to `Mirror`; coating stripe a hutch-keyed setting (Si 5-10, Rh 10-20, Pt 20-30 keV). | The mirror Asset detail. |
| ATTN-1 | Nice-to-have | The absorber-wedge attenuator and whether it folds into `Filter` or earns a distinct `Attenuator` kind (the fleet-wide question). | The wedge absorber bound to `Filter` (the i03 precedent). | The attenuator's catalog home. |

### Endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-go-live | The Newport kappa four-circle circle roles (phi / omega / kappa sample circles, the 2theta detector arm, det_z, the sample centring) and whether they compose an Assembly. | A `Goniometer` (kappa a setting) plus a 2theta detector arm; the `Assembly(Diffractometer)` is named, not built. | The diffractometer geometry; the CORA structural modelling is on [Model](#deliberately-not-here-yet). |
| DIFF-2 | Nice-to-have | The reciprocal-space coordination over the four-circle (the kappa-to-eulerian / hkl rule). | A reciprocal-space `PseudoAxis` over the circles, the rule deferred as on 4-ID / 8-ID / i06-1. | The reciprocal-space Asset. |
| SERIAL-1 | Nice-to-have | The serial / microfocus fixed-target arm (`BL19I-MO-SRL-01`, x / y / z / phi) and its raster sub-mode. | A second `Goniometer` for the serial / microfocus delivery; the fixed-target raster carried as a note. | The serial-arm modelling. |
| APERTURE-1 | Nice-to-have | The MAPT pinhole + collimator microfocus aperture and whether it binds `Aperture` (the i03 MAPT precedent) despite being a driven, size-selectable opening. | The pinhole + collimator bound to `Aperture`, the configuration sizes a Capability settings schema. | The aperture Family. |
| DET-1 | Blocks-go-live | The Eiger detector model, the OAV viewing-camera roles, the beamstops, and the backlight. | The Eiger and OAVs bind `Camera`; the beamstops bind `BeamStop`; the backlight binds the catalog `Backlight`. | The detector and viewing modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from dodal current and correct, and is the i19-blueapi arbiter the live optics-control path? | The handles in the descriptor are taken from dodal and carried confirm; the arbiter is the actuate seam (ACCESS-1). | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the photon / front-end shutters (absent from dodal beyond the interlocked optics shutter). | Permit leaves to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent of the shared optics. | Photon beam, cooling water, and vacuum on the optics. | The Supply observations. |
| GOV-1 | Nice-to-have | The Diamond operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the Diamond Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Does single-crystal diffraction (chemical crystallography) enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `diffraction` Method that 4-ID / 8-ID / CSX share; none coined. | The diffraction Capability. |
