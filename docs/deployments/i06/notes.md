# Notes

## Techniques

*What the modelled part of i06 is designed to do, as intent. Scaffold.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md#the-techniques-adapted-here) is how a facility adapts it. i06's techniques all sit in one family: polarization-driven dichroism. Every one of them turns the X-ray polarization at an absorption edge and reads the change in contrast, whether that contrast is an absorption spectrum, an electron image, or a diffraction peak. So i06's modelling story is not a new recipe over the spine; it is a new acquisition axis (the polarization) that the existing soft X-ray Methods now drive.

i06 is CORA's first APPLE-II source, so it is the first beamline that can set that axis at all. It is also CORA's first PEEM (photoemission electron microscopy) endstation, an electron-imaging technique whose defining instrument (the electron-optical column and its image detector) is not yet a CORA device (PEEM-1). The function view below survives both: it describes what each technique does, while the catalog vocabulary and the deferred instruments are carried as questions.

### The polarization-driven dichroism family

i06 carries four techniques, all pending in CORA's catalog. Two share Methods already pending from the 4-ID soft X-ray deployment; two are new pending slugs.

| Technique | CORA Method | Contrast it reads | Status in CORA |
| --- | --- | --- | --- |
| X-ray magnetic circular dichroism (XMCD) | `xmcd` | absorption difference between circular-positive and circular-negative polarization at a magnetic edge | shares the 4-ID `xmcd` Method, pending (TECH-1) |
| X-ray magnetic linear dichroism (XMLD) | `xmld` | absorption difference between two linear-polarization angles at a magnetic edge | new pending slug `xmld` (TECH-1) |
| Photoemission electron microscopy (PEEM) | `photoemission_microscopy` | magnified electron image of the photoemitting surface, with polarization-driven magnetic / electronic contrast | new pending slug, the imaging detector deferred (PEEM-1) |
| Resonant soft X-ray diffraction / dichroism | `resonant_scattering` | a diffraction peak whose intensity tracks order (magnetic / charge / orbital) as the polarization and energy are tuned through resonance | shares the 4-ID `resonant_scattering` Method, pending (TECH-1) |

Each technique adapts to i06 as a Site Practice on the [Diamond Site](../diamond/index.md#the-techniques-adapted-here): `I06_xmcd_practice`, `I06_xmld_practice`, `I06_peem_practice`, and `I06_resonant_diffraction_practice`, all pending. The Practices render unlinked until the owner decides whether each Method enters the catalog (TECH-1, PEEM-1).

A few points of intent shape the family:

- **The four techniques differ in what reads the contrast, not in how the contrast is made.** XMCD and XMLD read it as an absorption spectrum on the i06-1 stages; PEEM reads it as a magnified electron image at the i06-2 endstation; resonant diffraction reads it as the intensity of a Bragg peak on the i06-1 diffractometer. The shared move underneath all four is the same: set or turn the polarization at an absorption edge and observe the difference. That shared move is the new primitive (see below), and it is why XMCD and resonant scattering can reuse the Methods 4-ID already carries rather than coin i06-specific ones.

- **Two techniques reuse 4-ID Methods; two are new.** XMCD and resonant soft X-ray diffraction are the same Methods CORA already carries pending from the 4-ID deployment, so i06 is a second consumer rather than a coiner: the second consumer is the graduation watch-item for both. XMLD and photoemission microscopy have no existing Method that fits, so they are new pending slugs (`xmld`, `photoemission_microscopy`). Whether any of the four enters CORA's catalog as a Capability is an owner decision (TECH-1, PEEM-1).

- **PEEM is an imaging technique, and its instrument is not modelled yet.** PEEM is distinct from the electron-energy analysis of ARPES (the ESM endstation): ARPES analyses the energy and angle of photoelectrons, while PEEM forms a magnified spatial image of where they came from. The instrument that forms that image, the electron-optical column and its magnified electron-image detector, is absent from dodal and is deferred (PEEM-1). CORA models the PEEM sample manipulators now (they reuse the graduated `Manipulator` Family), and the column and image detector land once their PV handles are sourced. The `photoemission_microscopy` Method is the technique view of the same deferral: the recipe is named, the imaging instrument it would bind is not yet coined.

- **Resonant diffraction and XAS reuse the i06-1 geometry, and the detectors are deferred.** The i06-1 diffractometer (sample circles plus the detector arm) and the absorption stage are modelled now (DIFF-1, STAGE-1), but the i06-1 scattering detector and any incident-flux or drain-current electron-yield monitor are absent from dodal and are not invented (DET-1). So the techniques that read a diffraction peak or an absorption spectrum carry their detector as pending: the geometry that aims the beam is in the model, the device that records the signal is bound later.

### Polarization as a new operating axis for the fleet

The genuinely new thing i06 brings is not a Method; it is an axis. An APPLE-II undulator can drive its magnetic phase rows to choose the X-ray polarization, not just set a gap, so for the first time in the fleet a run can ask for a polarization the way it asks for an energy.

i06 models this as a [`PseudoAxis`](../../catalog/families.md), a sibling of the incident-energy pseudo-axis over the same source (the 2-BM beam-energy precedent, extended to a second driven source quantity). The shape is:

- **Set the polarization on the APPLE-II.** The axis's value domain is the polarization set the source can produce: linear horizontal (LH), linear vertical (LV), linear at an arbitrary angle (LA), circular positive (PC), circular negative (NC), plus third-harmonic variants (POL-1). The run names a value; CORA writes it; the source's phase rows move to produce it.

- **Flip or rotate it at an absorption edge to make the contrast.** XMCD flips between PC and NC at a magnetic edge and reads the absorption difference. XMLD rotates between two linear angles. Resonant diffraction tunes the polarization and the incident energy together through a resonance. In every case the contrast is the change the polarization causes, so turning the polarization at the edge is the acquisition primitive the whole dichroism family is built on.

- **The conversion stays on the live controller.** The polarization-to-phase kinematics (how a requested polarization becomes a phase-row position) is the axis's partition rule, and it is carried rule-less by default: the live i06 controller owns the conversion, so CORA names the axis and records the move without duplicating a second source of truth for the source geometry (POL-1). Pinning the conversion as a CORA-owned Calibration is deferred until a run needs to scan polarization without that controller in the loop. The same asymmetry the source-axis wiring carries (only the upstream IDU exposes the driven polarization handle in dodal) is an open question (POL-2).

This is the new acquisition primitive expressed entirely by reuse. The polarization axis is a `PseudoAxis` and the source is an `InsertionDevice`; no new device Family appears. What is new is that a run now carries a polarization alongside its energy, and the dichroism Methods drive both.

### Not modelled yet

The intent above is the function view. The concrete recipes that turn it into runnable acquisition are deliberately not written, because writing them for a beamline CORA does not yet drive would be invention rather than record:

- **The concrete dichroism recipes.** The per-edge energy and polarization sequences, the dwell and averaging, the field and temperature setpoints for an in-situ measurement, and the PEEM imaging sequence are calibration the deployment must supply. None of it is invented here.

- **Whether each Method enters the catalog.** Minting a Method is owner-scope. XMCD and resonant scattering reuse 4-ID Methods, and XMLD and photoemission microscopy are new slugs, but all four render pending until the owner decides (TECH-1, PEEM-1). The decision is recorded on the [Model](#model) page, not made here.

- **The PEEM imaging instrument.** The PEEM electron-optical column and its magnified electron-image detector are deferred (PEEM-1): they are the `ElectronMicroscope` anatomy, distinct from the photon `Camera` and from the energy-analyzing catalog `ElectronAnalyzer`, and they are not coined here because they have no PV in dodal.

- **The i06-1 detectors and flux monitor.** The diffraction scattering detector and the incident-flux / drain-current monitor are absent from dodal and are bound later from outside it, with no detector Family invented in the meantime (DET-1).

For the source and optics that feed these techniques, see the generated source-walk on [the beamline page](source.md). For what the i06 team must confirm before the model can be trusted, see [Open questions](#open-questions). The CORA-owned scope decisions (the polarization Calibration, the deferred Methods, the diffractometer Assembly) are recorded on the [Model](#deliberately-not-here-yet) page.

## Governance

*Who would act at i06, and the trust shape that would gate it. Scaffold.*

Governance at i06 follows the same model as the other Diamond beamlines: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

i06 is a further beamline at the Diamond Site, so it reuses the Diamond facility envelope rather than creating a new one: the operator pool, the safety review structure, and the safety forms are facility-wide and inherited, shared with the soft X-ray and MX siblings (I22, I03, I15-1, I11, I24). i06 adds only its own beamline-bound principals. The Diamond operator pool and review structure are site-level and shared across the beamlines, so they are not yet instantiated per beamline; they are carried pending on the [Diamond Site page](../diamond/index.md#safety-and-governance) (GOV-1). None of this is in dodal, which is a controls library, not an organizational record.

Because i06 is a reverse-engineered scaffold rather than a pilot, the concrete trust shape is not instantiated. What is already settled is the boundary, the same as for every deployment: clearances (the safety forms that must be active to start) are issued at the Diamond Site, not on the beamline, and the beamline links up to them rather than restating them. The Diamond personnel safety system (PSS) clearance is carried pending because its form names are not confirmed.

### The Enclosures i06 gates

The beamline spans three enclosures, the grouping CORA's Zone would follow (ENC-1):

| Enclosure | PV zone | What it holds |
| --- | --- | --- |
| i06-optics | BL06I (optics spine), SR06I (the APPLE-II servo crates) | the PGM, the twin APPLE-II controllers, and the i06-branch PEEM sample stage |
| i06-1 | BL06J | the diffraction-dichroism endstation |
| i06-2 | BL06K | the PEEM endstation |

How the two endstations share the source, and whether the three PV zones are three separate hutches, is the beamline team's to confirm (ENC-1). The Zone grouping is named here, not built.

### The safety tier behind the beam

The safety tier behind the beam is the personnel safety system. On a soft X-ray beamline the leaves that must be satisfied before the beam can enter an enclosure are the PSS search-and-secure permit signals, and the photon and front-end shutters are what those leaves gate. Both the permit signals and the shutters are absent from dodal, so CORA does not name them and does not invent them: the Enclosure permit signals and the shutters are carried pending (PSS-1). When staff confirm the signal and shutter handles, they bind to the Enclosure as the permit leaves the way the Diamond siblings carry theirs. No interlock, PSS, or equipment-protection tier is invented in the meantime.

The hazard classes i06 brings to that envelope are those of a soft X-ray UHV beamline:

- **An intense, variable-polarization beam.** i06 is the fleet's first APPLE-II source, so the beam's polarization is a driven experiment axis (LH / LV / PC / NC / LA plus third-harmonic variants over 70-2200 eV), not a fixed property. The radiation hazard is the standard photon-shutter concern the PSS gates (PSS-1); the polarization axis adds optics state, not a new safety tier.
- **Ultra-high vacuum on the optics and both endstations.** The soft X-ray optics and the two endstations run under UHV (SUP-1). The hazard is the vacuum envelope itself, the same class the PEEM and diffraction-dichroism endstations carry.
- **In-situ temperature environments.** The i06-1 endstation carries two Lakeshore 336 controllers for sample cooling and heating (TEMP-1). The sample environment spans a temperature range whose limits are pending; the hazard is the cryogen and heater envelope at the sample.

Where these become Clearance-gated operation (for example any unattended or hazardous run) is the shape the Diamond siblings reserve, not instantiated here.

### What is deliberately not modelled

- **The PSS permit signals and shutters (PSS-1).** Absent from dodal, carried pending, not invented.
- **The Diamond operator pool and review structure (GOV-1).** Site-level and shared across the beamlines, carried pending on the Diamond Site, not instantiated per beamline.
- **The concrete Zone, Conduit, and Policy instances.** Named as the trust shape, not built; they would land if and when the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

The deferred detectors (the i06-1 scattering detector and the PEEM electron-image column, DET-1 and PEEM-1) are equipment, not governance, decisions; they live on [Model](#deliberately-not-here-yet). The full delete-on-answer queue is on [Open questions](#open-questions).

## Model

*The developer's by-kind index: where each CORA aggregate's i06 content lives, why this first APPLE-II deployment coins no new family and models polarization as an axis, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at i06 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the polarization PseudoAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes i06 new

i06 is CORA's first APPLE-II (variable-polarization) source. The fleet's other insertion devices set a gap; an APPLE-II additionally drives its magnetic phase rows to choose the X-ray polarization, so i06 is the first beamline whose run sets the polarization as an experiment axis: linear horizontal or vertical, linear at an arbitrary angle, circular positive or negative, and third-harmonic variants. That is what magnetic dichroism needs (the X-ray magnetic circular and linear dichroism contrast comes from flipping or rotating the polarization at an absorption edge). i06 is also CORA's first PEEM (photoemission electron microscopy) endstation, an electron-imaging technique distinct from the electron-energy analysis of ARPES.

The novelty forces no new device families. It is carried by two reuse decisions and two deferrals (below). The genuinely new modelling primitive, polarization as a driven axis, is expressed by reusing the existing `PseudoAxis` Family, the same way incident energy is already a pseudo-axis.

### No new families

i06 coins no new Family and changes nothing in the catalog. The four devices that could have tempted a new kind all fold into existing vocabulary:

- **The two APPLE-II undulators bind the catalog `InsertionDevice`, not a new source family.** An APPLE-II is the same source-undulator anatomy as the EPUs already bound by SIX, CSX, and ESM. The catalog `InsertionDevice` Family already "spans the undulator and the wiggler; the device type and its gap / field parameters are a per-Asset settings difference." The APPLE-II variable-polarization phase rows, the EPICS energy-to-gap polynomial lookup, and the coordinating controller are per-Asset settings and the bound Model (they are how the gap and phase are driven), not a new device class. This resolves the long-standing `SRC-1` question toward reuse: a second concordant variable-polarization source confirms the existing Family stretches, rather than earning a split.

- **Polarization is a `PseudoAxis`, not a new primitive.** The thing an i06 run sets, the polarization, is modelled as a `PseudoAxis` Asset, a sibling of the incident-energy pseudo-axis over the same source. The polarization value domain (LH / LV / PC / NC / LA plus third-harmonic variants) is the axis's value set, and the controller's polarization-to-phase conversion is its partition rule. This is exactly the 2-BM beam-energy-as-pseudo-axis precedent, extended to a second driven source quantity. CORA names the axis, writes the value, and records the move; by default the live i06 controller owns the polarization-to-phase kinematics (the partition rule is carried rule-less, `POL-1`), so CORA does not duplicate a second source of truth for the optics geometry.

- **The PEEM sample manipulators bind the graduated `Manipulator`.** The PEEM endstation's UHV sample manipulators (x / y / phi plus the energy-slit translation) reuse the `Manipulator` Family graduated on SIX and ESM; the energy-slit axis and axis count are per-Asset settings.

- **The PGM binds `GratingMonochromator`, the diffractometer binds `Goniometer`, the Lakeshores bind `TemperatureController`.** All three reuse families the soft X-ray and diffraction siblings already earned.

### Deliberately not here yet

- **The PEEM electron-imaging column and detector (`PEEM-1`).** The PEEM technique's defining instrument, the electron-optical column that forms a magnified electron image of the photoemitting surface, is not a dodal device (dodal binds the PEEM sample manipulator and its energy slit, not the column or the image detector). It is the `ElectronMicroscope` anatomy: an electron-imaging column, distinct from the photon `Camera` (which produces a Frame from photons) and from the energy-analyzing catalog `ElectronAnalyzer` (the ESM / ARPES electron-energy analyzer). It is deferred as `PEEM-1`, not coined: binding a family with no PV would create an orphan, so the column and detector land once their handles are sourced. i06's PEEM branch is then a candidate first sighting for an `ElectronMicroscope` family.

- **The i06-1 diffraction detector and the flux monitors (`DET-1`).** The i06-1 scattering detector and any incident-flux or drain-current (electron-yield) monitor are absent from dodal (only the detector-arm motors are present). The geometry is modelled now; the detectors are bound later from outside dodal, and no detector Family is invented in the meantime.

- **The diffractometer Assembly (`DIFF-1`).** Whether the i06-1 sample circles plus the detector arm compose an `Assembly(Diffractometer)` is deferred, exactly as 4-ID, 8-ID, and CSX deferred materializing their soft X-ray diffractometer Assemblies in descriptor mode. The first cut is a flat `Goniometer` Asset plus a reciprocal-space `PseudoAxis`, with the Assembly named as the follow-on.

- **The XMCD / XMLD / PEEM Methods.** Whether magnetic dichroism, photoemission microscopy, and resonant soft X-ray diffraction enter CORA's catalog as Capabilities / Methods is an owner decision; the Practices render unlinked, pending. XMCD and resonant scattering share the 4-ID Methods; XMLD and photoemission microscopy are new pending slugs (`TECH-1`, `PEEM-1`).

- **The polarization Calibration (`POL-1`).** Pinning the polarization-to-phase conversion as a CORA-owned LookupTable Calibration revision (rather than letting the live i06 controller own it) is deferred; it is only needed if CORA must scan polarization without the i06 controller in the loop.

- **The simulated devices and full asset-tree scenarios.** No `test_i06_*.py` registers the asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the i06 team to confirm before the model can be trusted.*

i06 was reverse-engineered from the beamline's own bluesky device layer ([DiamondLightSource/dodal](https://github.com/DiamondLightSource/dodal): the `src/dodal/beamlines/i06*.py` factories and the `src/dodal/devices/` classes), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from dodal rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are the PV zones BL06I (optics spine), BL06J (i06-1), and BL06K (i06-2) three separate hutches, and how do the two endstations share the source? | Three enclosures: a shared `i06-optics` zone and the `i06-1` and `i06-2` experiment hutches. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The two APPLE-II undulator periods, the gap range, and how the downstream (IDD) and upstream (IDU) devices coordinate to feed the branches. | Two `InsertionDevice` Assets; period and coordination carried pending. | The source Asset detail. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state i06 reads (current, fill, machine mode). | Observe-only machine state on `SR-DI-DCCT-01` / `CS-CS-MSTAT-01` / `SR-CS-FILL-01`, a loose `StorageRing`. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The plane-grating monochromator gratings (line densities), the cff fixed-focus constant, and the incident-energy range and partition rule. | A soft X-ray PGM bound to `GratingMonochromator`, 70-2200 eV, gratings 150 / 400 / 1200 l/mm; the energy pseudo-axis decomposes to the PGM and the APPLE-II gap. | The monochromator and incident-energy Assets. |
| POL-2 | Blocks-go-live | The IDD / IDU asymmetry: only the upstream IDU exposes the driven energy / polarization handles in dodal, while the downstream IDD stops at its controller. Should CORA expose a symmetric IDD handle? | The energy and polarization pseudo-axes are over the upstream IDU; the IDD is a sibling `InsertionDevice` Asset. | The source-axis wiring. |

### Beam axes: polarization

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| POL-1 | Blocks-go-live | The polarization value domain (LH / LV / PC / NC / LA plus third-harmonic variants) and the polarization-to-phase conversion: should CORA pin the conversion as a LookupTable Calibration, or run the polarization pseudo-axis rule-less and let the live i06 controller own the kinematics? | A `PseudoAxis` over the APPLE-II phase rows, value domain as listed, carried rule-less by default (the controller owns the conversion). | The polarization-axis modelling. |

### Diffraction-dichroism endstation (i06-1)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-go-live | The i06-1 diffraction-dichroism circle roles (sample theta incidence, chi / phi orientation, the DET:2THETA / DET:Y detector arm) and whether they compose an Assembly. | A `Goniometer` for the sample circles plus a detector arm; the `Assembly(Diffractometer)` is named, not built. | The diffractometer geometry; the CORA structural modelling is on [Model](#deliberately-not-here-yet). |
| DIFF-2 | Nice-to-have | The reciprocal-space coordination over the diffraction-dichroism circles (the inverse-kinematics rule). | A reciprocal-space `PseudoAxis` over the circles, the rule deferred as on 4-ID / 8-ID / CSX. | The reciprocal-space Asset. |
| STAGE-1 | Nice-to-have | Whether the absorption-stage theta (and the diffractometer chi / phi) warrant a `Goniometer` plus Assembly rather than the `LinearStage` placeholder. | The absorption stage bound to `LinearStage` as a design-phase placeholder. | The absorption-stage Family. |
| TEMP-1 | Nice-to-have | The Lakeshore 336 cooling and heating ranges and channel assignment. | Two `TemperatureController` Assets presenting the `Regulator` Role; cooling-vs-heating a per-Asset setting; ranges pending. | The temperature-control modelling. |
| DET-1 | Blocks-go-live | The i06-1 diffraction scattering detector and any incident-flux / drain-current (electron-yield) monitor: both are absent from dodal. | Not modelled as devices: the geometry is modelled now and the detector(s) bound later from outside dodal; no detector Family invented. | The detector modelling. |

### PEEM endstation (i06-2)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MANIP-1 | Blocks-go-live | The PEEM sample-manipulator axis sets (the i06-2 `peem` x / y / phi plus the es energy-slit translation, and the i06-branch sample stage). | Two `Manipulator` Assets reusing the graduated Family; axis sets carried pending. | The manipulator modelling. |
| PEEM-1 | Blocks-go-live | The PEEM electron-optical column and its magnified electron-image detector: both are absent from dodal. | Not modelled: the electron-imaging column is the `ElectronMicroscope` anatomy, deferred until its PVs are sourced; not coined here. | The PEEM imaging-detector modelling; the CORA family decision is on [Model](#deliberately-not-here-yet). |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from dodal current and correct? | The handles in the descriptor are taken from dodal and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the photon / front-end shutters (absent from dodal). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (the soft X-ray optics and the UHV endstations) and the cooling supply. | Photon beam, cooling water, and ultra-high vacuum on the optics and endstations. | The Supply observations. |
| GOV-1 | Nice-to-have | The Diamond operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the Diamond Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do the soft X-ray dichroism and resonant-scattering techniques (XMCD, XMLD, resonant diffraction) enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices; XMCD and resonant scattering share the 4-ID Methods, XMLD is a new pending slug; none coined. | The dichroism / resonant Capabilities. |
