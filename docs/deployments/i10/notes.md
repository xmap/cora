# Notes

## Techniques

*What the modelled part of i10 is designed to do, as intent. Scaffold.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md#the-techniques-adapted-here) is how a facility adapts it. i10 (BLADE) is i06's soft X-ray twin: the fleet's second APPLE-II source, sharing the twin-APPLE-II and PGM spine, feeding two endstations that study magnetic materials. Its techniques sit in the same family i06 already named, polarization-driven contrast, but i10 reads that contrast two ways i06 does not: it resolves the polarization of the scattered beam (the RASOR analyzer arm), and it makes the contrast under an applied magnetic field at low temperature (the i10-1 magnets).

So i10's modelling story is mostly reuse. The polarization acquisition axis already exists from i06, and three of i10's four Methods are already pending in CORA's catalog. What i10 adds on top is two affordances, polarization analysis and applied-field dichroism, expressed against families CORA already carries rather than new recipes over the spine. The function view below describes what each technique does, while the catalog vocabulary and the deferred decisions are carried as questions.

### The four techniques

i10 carries four techniques, all pending in CORA's catalog. Three reuse Methods already pending from earlier soft X-ray deployments; one is a new pending slug.

| Technique | CORA Method | Contrast it reads | Status in CORA |
| --- | --- | --- | --- |
| Resonant soft X-ray scattering | `resonant_scattering` | a diffraction peak whose intensity tracks magnetic / charge / orbital order as the polarization and energy are tuned through resonance | shares the 4-ID `resonant_scattering` Method, pending (TECH-1) |
| Soft X-ray reflectivity | `reflectivity` | the specularly reflected intensity versus angle and energy, sensitive to depth structure and magnetic profile (the R in RASOR) | new pending slug `reflectivity` (TECH-1) |
| X-ray magnetic circular dichroism (XMCD) | `xmcd` | absorption difference between circular-positive and circular-negative polarization at a magnetic edge, here in an applied field | shares the 4-ID `xmcd` Method, pending (TECH-1) |
| X-ray magnetic linear dichroism (XMLD) | `xmld` | absorption difference between two linear-polarization angles at a magnetic edge, here in an applied field | shares the i06 `xmld` slug, pending (TECH-1) |

Each technique adapts to i10 as a Site Practice on the [Diamond Site](../diamond/index.md#the-techniques-adapted-here): `I10_resonant_scattering_practice`, `I10_reflectivity_practice`, `I10_xmcd_practice`, and `I10_xmld_practice`, all pending. The Practices render unlinked until the owner decides whether each Method enters the catalog (TECH-1).

A few points of intent shape the four:

- **The four split across two endstations by what reads the contrast.** Resonant scattering and reflectivity read it at the RASOR endstation: the contrast is the intensity of a scattered or reflected beam on the diffractometer, observed through point and current-integrating detection (DET-1). XMCD and XMLD read it at the i10-1 / I10J magnet endstation: the contrast is an absorption difference observed as total-electron-yield, fluorescence, or diode signal while a magnetic field is applied to the sample (DET-1, MAG-1). Underneath all four is the same shared move that i06 named: set or turn the polarization at an absorption edge and observe the difference.

- **Three techniques reuse existing Methods; one is new.** Resonant scattering and XMCD are the same Methods CORA already carries pending from the 4-ID deployment, and XMLD reuses the i06 slug, so for those three i10 is a second (or third) consumer rather than a coiner: the second consumer is the graduation watch-item. Reflectivity has no existing Method that fits, so it is a new pending slug. Whether any of the four enters CORA's catalog as a Capability is an owner decision (TECH-1), recorded on the [Model](#model) page, not made here.

- **Resonant scattering and reflectivity reuse the RASOR geometry, and the science detector is a flux monitor.** The RASOR diffractometer (the two-theta scattering arm with sample theta, chi, chamber X, and alpha) is modelled now as a `Goniometer` (DIFF-1), with a reciprocal-space `PseudoAxis` over it (DIFF-2). There is no area detector at RASOR, so the scattered-beam point detector, the incident-flux monitor, the fluorescence channel, and the drain-current / total-electron-yield channel all bind the catalog `FluxMonitor` family through their current amplifiers (DET-1). The geometry that aims and reads the beam is in the model; the recipe that sequences a scan or a reflectivity curve is calibration the deployment supplies later.

- **XMCD and XMLD here are field-and-temperature techniques.** At i10-1 the contrast is made not just by turning the polarization but by applying a magnetic field with the sample held cold. The magnets are modelled (MAG-1), the cryostat stage and its temperature controller are modelled (TEMP-1), and the i10-1 point detection is again a `FluxMonitor` (DET-1). The applied-field affordance is what distinguishes i10's XMCD / XMLD from i06's, and it is the second of the two things i10 adds (see below).

### The polarization axis, reused from i06

The polarization acquisition axis is not new with i10. i06 brought it to the fleet first: an APPLE-II undulator drives its magnetic phase rows to choose the X-ray polarization, not just set a gap, so a run can ask for a polarization the way it asks for an energy. i10 is the fleet's second APPLE-II source and reuses that axis unchanged.

i10 models it as a [`PseudoAxis`](../../catalog/families.md) over the twin-APPLE-II phase rows, a sibling of the incident-energy pseudo-axis over the same source. The shape is:

- **Set the polarization on the APPLE-II.** The axis's value domain is the polarization set the source can produce: linear horizontal (LH), linear vertical (LV), circular positive (PC), circular negative (NC), and linear at an arbitrary angle (LA), plus third-harmonic variants (POL-1). The continuous linear-arbitrary-angle is the continuous realization of the LA value within this same axis, not a second axis and not a new family. The run names a value; CORA writes it; the source's phase rows move to produce it.

- **Turn it at an absorption edge to make the contrast.** XMCD flips between PC and NC at a magnetic edge and reads the absorption difference. XMLD rotates between two linear angles. Resonant scattering tunes the polarization and the incident energy together through a resonance. In every case the contrast is the change the polarization causes, so turning the polarization at the edge is the acquisition primitive the whole family is built on.

- **The conversion stays on the live controller.** The polarization-to-phase kinematics is carried rule-less by default: the live i10 controller owns the conversion, so CORA names the axis and records the move without duplicating a second source of truth for the source geometry (POL-1). Both undulators are driven sources, and whether the polarization handle is wired over one axis or two is an open question (ENERGY-1).

So far this is i06's primitive expressed by reuse: the polarization axis is a `PseudoAxis`, the source is an `InsertionDevice`, and no new device Family appears. i10 then adds two things i06 does not carry.

#### What i10 adds: polarization analysis of the scattered beam

RASOR does not only set the incident polarization; it can resolve the polarization of the scattered beam. The motorized analyzer arm (the PaStage / POLAN arm, with its analyzer two-theta and theta, py and pz, and eta motors) selects a scattered-polarization channel, which is what lets resonant scattering separate the magnetic and charge contributions to a peak rather than read only its total intensity. This is the analysis half of polarization: i06 turns it, i10 also reads it back.

CORA models that arm as the catalog `PolarizationAnalyzer` Family. This is a deliberate modelling choice: dodal exposes only the arm's motors, and the analyzer crystal is implicit hardware, but RASOR's defining polarization-analysis role lives on that real motorized arm, so CORA models the arm rather than hiding the role. The analyzer crystal specifics are not invented (POL-2). The Family has graduated across 4-ID / i10 / ID32 / P09, presenting Positioner; the analyzer-crystal spec stays a per-Asset detail to confirm (POL-2).

#### What i10 adds: applied-field dichroism

The i10-1 / I10J endstation makes the dichroic contrast under an applied magnetic field, with the sample held at low temperature. Two magnet devices serve it: a set-and-read electromagnet and a superconducting magnet whose field can be swept (a Flyable affordance). CORA models both as the single graduated `Magnet` family: they are one family, and the field sweep is a per-Asset affordance, not a split (MAG-1). i10-1 was the `Magnet` family's second sighting after 4-ID, and with the later ESRF ID32 magnet it reached a rule-of-three and graduated into the catalog (MAG-1). The field values and the sweep specifics are not invented (MAG-1).

The applied field is what makes i10's XMCD / XMLD different from i06's: i06 reads dichroism from the polarization alone, while i10 reads it with a field applied and the sample cold. The cryostat low-temperature stage folds into the catalog `LinearStage`, and the magnet temperature is held by a catalog `TemperatureController` (TEMP-1). As with the polarization axis, no new device Family is coined for either addition: the analyzer binds the graduated catalog `PolarizationAnalyzer`, and the magnets are the graduated `Magnet` family, whose rule-of-three i10-1 helped complete.

### Not modelled yet

The intent above is the function view. The concrete recipes that turn it into runnable acquisition are deliberately not written, because writing them for a beamline CORA does not yet drive would be invention rather than record:

- **The concrete recipes.** The per-edge energy and polarization sequences, the reflectivity angle and energy scans, the polarization-analysis channel selections, the field and temperature setpoints for an in-situ measurement, and the dwell and averaging are all calibration the deployment must supply. None of it is invented here. No energies, angles, fields, or resolutions are stated.

- **Whether each Method enters the catalog.** Minting a Method is owner-scope. Resonant scattering and XMCD reuse 4-ID Methods, XMLD reuses the i06 slug, and reflectivity is a new slug, but all four render pending until the owner decides (TECH-1). The decision is recorded on the [Model](#model) page, not made here.

- **The graduated analyzer and magnet families.** `PolarizationAnalyzer` has graduated to a catalog Family across 4-ID / i10 / ID32 / P09 (POL-2), so i10's analyzer arm binds the catalog Family; the analyzer-crystal spec stays uninvented as a per-Asset detail. The `Magnet` family has also graduated (i10-1 was one of its three consumers with 4-ID and ID32), so i10's magnets bind the catalog Family; only the per-Asset magnet field values stay uninvented (MAG-1).

- **The science detectors.** Neither endstation has an area detector. The RASOR and i10-1 point and current-integrating channels bind the catalog `FluxMonitor` through their current amplifiers (DET-1); no detector Family is invented in the meantime.

For the source and optics that feed these techniques, see the generated source-walk on [the beamline page](source.md). For what the i10 team must confirm before the model can be trusted, see [Open questions](#open-questions). The CORA-owned scope decisions (the deferred Methods, the held families, the diffractometer Assembly) are recorded on the [Model](#deliberately-not-here-yet) page.

## Governance

*Who would act at i10, and the trust shape that would gate it. Scaffold.*

Governance at i10 follows the same model as the other Diamond beamlines: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

i10 is a further beamline at the Diamond Site, so it reuses the Diamond facility envelope rather than creating a new one: the operator pool, the safety review structure, and the safety forms are facility-wide and inherited, shared with the soft X-ray and MX siblings (I22, I03, I15-1, I11, I24, I06). i10 adds only its own beamline-bound principals. The Diamond operator pool and review structure are site-level and shared across the beamlines, so they are not yet instantiated per beamline; they are carried pending on the [Diamond Site page](../diamond/index.md#safety-and-governance) (GOV-1). None of this is in dodal, which is a controls library, not an organizational record.

Because i10 is a reverse-engineered scaffold rather than a pilot, the concrete trust shape is not instantiated. What is already settled is the boundary, the same as for every deployment: clearances (the safety forms that must be active to start) are issued at the Diamond Site, not on the beamline, and the beamline links up to them rather than restating them. The Diamond personnel safety system (PSS) clearance is carried pending because its form names are not confirmed.

i10 is i06's soft X-ray twin: the two beamlines share a twin-APPLE-II and PGM spine and feed branch endstations. The governance shape is the same on both, and i10 inherits it the same way, so this page reads as the i06 page does, with the hazard classes that are particular to i10 called out below.

### The Enclosures i10 gates

The beamline spans three enclosures, the grouping CORA's Zone would follow (ENC-1):

| Enclosure | PV zone | What it holds |
| --- | --- | --- |
| i10-optics | BL10I (optics spine), SR10I (the APPLE-II servo crates) | the PGM, the twin APPLE-II controllers, and the collimating and switching mirrors |
| i10-rasor | ME01D | the RASOR resonant-scattering and reflectivity endstation, with its branch focusing mirror |
| i10-1 / I10J | BL10J | the magnet endstation, with its electromagnet and superconducting magnet |

How the two endstations share the source, and whether the three PV zones are three separate hutches, is the beamline team's to confirm (ENC-1). The Zone grouping is named here, not built.

### The safety tier behind the beam

The safety tier behind the beam is the personnel safety system. On a soft X-ray beamline the leaves that must be satisfied before the beam can enter an enclosure are the PSS search-and-secure permit signals, and the photon and front-end shutters are what those leaves gate. Both the permit signals and the shutters are absent from dodal, so CORA does not name them and does not invent them: the Enclosure permit signals and the shutters are carried pending (PSS-1). When staff confirm the signal and shutter handles, they bind to the Enclosure as the permit leaves the way the Diamond siblings carry theirs. No interlock, PSS, or equipment-protection tier is invented in the meantime.

The hazard classes i10 brings to that envelope are those of a soft X-ray UHV beamline, plus the magnet endstation's own:

- **An intense, variable-polarization beam.** i10 is the fleet's second APPLE-II source, after i06, so the beam's polarization is a driven experiment axis (LH / LV / PC / NC / LA plus third-harmonic variants, with the continuous linear-arbitrary-angle the realization of the LA value within the same axis) rather than a fixed property (POL-1). The radiation hazard is the standard photon-shutter concern the PSS gates (PSS-1); the polarization axis adds optics state, not a new safety tier.
- **Ultra-high vacuum on the optics and the endstations.** The soft X-ray optics run under UHV (SUP-1). The hazard is the vacuum envelope itself, the same class the Diamond soft X-ray siblings carry.
- **High magnetic fields at i10-1.** The i10-1 / I10J endstation carries an electromagnet (BL10J-EA-MAGC-01) and a superconducting magnet whose field can be swept (BL10J-EA-SMC-01), both modelled on the graduated catalog Magnet family (MAG-1). A superconducting magnet is a high-field environment, a class of hazard the optics and the RASOR endstation do not carry. CORA does not invent field values or sweep specifics (MAG-1); what it records is that this endstation adds a hazard class the rest of the beamline does not have.
- **Cryogenics at the sample.** The RASOR sample sits on a cryostat stage (ME01D-MO-CRYO-01) read by a Lakeshore 340 (ME01D-EA-TCTRL-01), and the i10-1 magnet endstation folds a cryostat low-temperature environment into its stages, read by a Lakeshore 336 (BL10J-EA-TCTRL-41) (TEMP-1). The hazard is the cryogen and low-temperature envelope at the sample, the same class the soft X-ray siblings carry, here paired with the magnet field at i10-1.

Where these become Clearance-gated operation (for example any unattended or hazardous run, or a superconducting-magnet field sweep) is the shape the Diamond siblings reserve, not instantiated here.

### What is deliberately not modelled

- **The PSS permit signals and shutters (PSS-1).** Absent from dodal, carried pending, not invented.
- **The Diamond operator pool and review structure (GOV-1).** Site-level and shared across the beamlines, carried pending on the Diamond Site, not instantiated per beamline.
- **The concrete Zone, Conduit, and Policy instances.** Named as the trust shape, not built; they would land if and when the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

The RASOR analyzer arm binds the catalog `PolarizationAnalyzer` (graduated, POL-2); the analyzer-crystal spec is an equipment, not governance, detail. The graduated `Magnet` family (the magnet devices, MAG-1) is likewise equipment modelling; they live on [Model](#model). The full delete-on-answer queue is on [Open questions](#open-questions).

## Model

*The developer's by-kind index: where each CORA aggregate's i10 content lives, why this second APPLE-II deployment coins no new family and decides two loose families' second sighting, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at i10 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the polarization PseudoAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes i10 new

i10 is the fleet's second APPLE-II (variable-polarization) source, after i06, and it is i06's soft X-ray twin: the same shared spine of twin APPLE-II undulators feeding a plane-grating monochromator and two branch endstations. What i10 adds is the science those endstations do with the polarization: resonant soft X-ray scattering and reflectivity on the RASOR diffractometer (with a polarization-analysis arm that resolves the polarization of the scattered beam), and X-ray magnetic dichroism with the sample in an applied magnetic field at the i10-1 endstation.

For the modelling, i10's significance is that it brings two device families that were loose at a single beamline (4-ID) to a second sighting: the polarization analyzer and the sample-environment magnet. That second independent deployment was a step toward the rule-of-three; both families have since completed it and graduated into the catalog (PolarizationAnalyzer across 4-ID / i10 / ID32 / P09, Magnet across 4-ID / i10-1 / ID32), so i10's analyzer arm and magnets bind their catalog Families. i10 coins no new family.

### No new families

i10 coins no new Family and changes nothing in the catalog.

- **The polarization decisions follow the merged i06 precedent.** The two APPLE-II undulators bind the catalog `InsertionDevice` (the phase rows, the energy-to-gap polynomial, and the controller are per-Asset settings and the bound Model). The polarization is a `PseudoAxis` Asset, a sibling of the incident-energy axis over the same source; the Pol value domain (LH / LV / PC / NC / LA plus third-harmonic variants) is the axis's value set, and the controller's polarization-to-phase conversion is its partition rule, carried rule-less (`POL-1`). i10's one addition over i06 is the continuous linear-arbitrary-angle: it is the continuous realization of the LA value within the same polarization axis, not a second axis, since the angle is meaningful only as a refinement of LA.
- **The RASOR sample circles bind `Goniometer`, with a reciprocal-space `PseudoAxis`** (the 4-ID / 8-ID / i06-1 diffractometer pattern; the Assembly is named, not built, `DIFF-1`).
- **The rest reuse existing families:** the PGM binds `GratingMonochromator`; the collimating, switching, and focusing mirrors bind `Mirror`; the slits bind `Slit`; the pinhole binds `Aperture`; the sample and magnet stages bind `LinearStage`; the Lakeshore controllers bind `TemperatureController`; and the counting chains bind `FluxMonitor`. The machine state reuses the loose `StorageRing`.

### Loose families at a second sighting

Two families that were used only at 4-ID reach a further sighting at i10, and both have since graduated. The promotion guard (`PROMOTION_THRESHOLD = 2`) makes a loose family used by two or more deployments require a recorded hold-or-graduate decision: the signal is mechanical, the decision stays human. `Magnet` has graduated: i10-1 was one of the three consumers (with 4-ID and ESRF ID32) whose rule-of-three earned it into the catalog, so i10's magnets now bind the graduated catalog `Magnet` Family (it presents the `Regulator` Role, the field a settable process variable). `PolarizationAnalyzer` has also graduated to a catalog Family (earned across 4-ID / i10 / ID32 / P09, presenting Positioner), so i10's RASOR arm now binds the catalog Family.

| Loose family | Sightings | i10 binding | Decision |
| --- | --- | --- | --- |
| `PolarizationAnalyzer` | 4-ID, i10, ID32, P09 | the RASOR polarization-analysis arm (the POLAN stage) | **graduated** (`POL-2`): catalog Family across 4-ID / i10 / ID32 / P09, presents Positioner; dodal exposes the analyzer arm's motors only (the analyzer crystal is implicit hardware), so CORA models the role on the real motorized arm and binds the catalog Family |
| `Magnet` | 4-ID, i10 (i10-1), ID32 | the i10-1 electromagnet and the superconducting field-sweep magnet | **graduated** (`MAG-1`): i10-1 was one of the three consumers (4-ID + i10-1 + ID32) whose rule-of-three earned it; both magnet devices are one Family, the field-sweep capability is a per-Asset bound-Model affordance, not a split (the `InsertionDevice` / `TemperatureController` precedent); presents the `Regulator` Role (`MAG-1` now covers only the per-Asset field detail) |

The decision to bind the RASOR PaStage to the catalog `PolarizationAnalyzer` Family (rather than to a plain detector-arm `RotaryStage` with the analyzer as a setting) is a deliberate one: RASOR's defining role is polarization analysis (the PV root is `POLAN`), and CORA models that role on the real arm rather than hiding it in a note. The absence of an analyzer-crystal signal in dodal is an absence in the data, not proof the role is absent; the analyzer-crystal spec stays a per-Asset detail to confirm (`POL-2`).

### Deliberately not here yet

- **No area detector; the science detector is a point counter (`DET-1`).** Neither endstation has an area detector in dodal. Detection is point and current-integrating: the scattered-beam point detector, the incident-flux monitor, and the fluorescence and drain-current / total-electron-yield channels are current-amplifier-plus-scaler chains, which bind `FluxMonitor`. Whether scattered-beam point-counting eventually earns its own Sensor Family is `DET-1`; if a future i10 area detector appears, the science detector migrates.
- **The diffractometer Assembly (`DIFF-1`) and the reciprocal-space rule (`DIFF-2`).** Named, not built, exactly as 4-ID, 8-ID, and i06-1 deferred theirs.
- **The polarization Calibration (`POL-1`).** Pinning the polarization-to-phase and the linear-arbitrary-angle conversion as a CORA-owned Calibration is deferred; it is only needed if CORA must scan polarization without the i10 controller in the loop.
- **The resonant-scattering / reflectivity / XMCD / XMLD Methods.** Whether they enter CORA's catalog is an owner decision; the Practices render unlinked, pending. Resonant scattering and XMCD share the 4-ID Methods, XMLD shares the i06 slug, and reflectivity is a new pending slug (`TECH-1`).
- **The upstream diagnostics and simulated devices.** The diagnostic screens (d1-d7 fluorescent screens and webcams) and the simulated devices are not modelled in this cut; no `test_i10_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the i10 team to confirm before the model can be trusted.*

i10 was reverse-engineered from the beamline's own bluesky device layer ([DiamondLightSource/dodal](https://github.com/DiamondLightSource/dodal): the `src/dodal/beamlines/i10*.py` factories and the `src/dodal/devices/` classes), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from dodal rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are the PV zones BL10I (optics spine), ME01D (RASOR), and BL10J (i10-1) three separate hutches, and how do the two endstations share the source? | Three enclosures: a shared `i10-optics` zone and the `i10-rasor` and `i10-1` experiment hutches. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The two APPLE-II undulator periods, the gap range, and how the downstream (IDD) and upstream (IDU) devices feed the branches. | Two `InsertionDevice` Assets; period carried pending. | The source Asset detail. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state i10 reads (current, energy, fill). | Observe-only machine state, a loose `StorageRing`; the exact PVs pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The plane-grating monochromator gratings, the cff constant, and the incident-energy range and partition rule. | A soft X-ray PGM bound to `GratingMonochromator`; gratings and range pending. | The monochromator and incident-energy Assets. |

### Beam axes: energy and polarization

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENERGY-1 | Nice-to-have | Both APPLE-IIs are driven sources (energy_dd over IDD, energy_ud over IDU); should CORA carry one incident-energy axis or two, and how do they map to the branches? | One `BeamEnergy` `PseudoAxis` over the PGM and the APPLE-II gap; the two-source wiring pending. | The incident-energy Asset wiring. |
| POL-1 | Blocks-go-live | The polarization value domain (LH / LV / PC / NC / LA plus third-harmonic variants and the continuous linear-arbitrary-angle) and the polarization-to-phase conversion: pin it as a CORA Calibration, or run the axis rule-less and let the live controller own it? | A `PseudoAxis` over the APPLE-II phase rows; the linear-arbitrary-angle is the continuous realization of LA in the same axis; rule-less by default. | The polarization-axis modelling. |

### RASOR endstation (i10-rasor)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-go-live | The RASOR diffractometer circle roles (two-theta scattering arm, sample theta / chi, chamber X, alpha) and whether they compose an Assembly. | A `Goniometer` for the sample circles; the `Assembly(Diffractometer)` is named, not built. | The diffractometer geometry; the CORA structural modelling is on [Model](#deliberately-not-here-yet). |
| DIFF-2 | Nice-to-have | The reciprocal-space coordination over the RASOR circles (the inverse-kinematics rule). | A reciprocal-space `PseudoAxis` over the circles, the rule deferred as on 4-ID / 8-ID / i06-1. | The reciprocal-space Asset. |
| POL-2 | Blocks-go-live | Does RASOR run genuine polarization analysis on the PaStage (the POLAN arm), confirming the analyzer-crystal spec on the catalog `PolarizationAnalyzer` Family? | The PaStage binds the catalog `PolarizationAnalyzer` (graduated across 4-ID / i10 / ID32 / P09); dodal exposes the motors only, the analyzer crystal is implicit, so the crystal spec stays a per-Asset detail to confirm. | The analyzer-crystal spec; the graduation is recorded on [Model](#loose-families-at-a-second-sighting). |
| STAGE-1 | Nice-to-have | Whether the cryostat sample stage warrants a `Manipulator` rather than `LinearStage`, and whether the pinhole is an `Aperture` or a plain stage. | The sample stage bound to `LinearStage` (plain in-air translation); the pinhole bound to `Aperture`. | The sample-stage and pinhole Families. |
| TEMP-1 | Nice-to-have | The Lakeshore 340 (RASOR) and Lakeshore 336 (i10-1) temperature ranges and channel assignment. | Two `TemperatureController` Assets presenting the `Regulator` Role; ranges pending. | The temperature-control modelling. |
| DET-1 | Blocks-go-live | The RASOR and i10-1 detection: no area detector exists in dodal, only the current-amplifier / scaler point-counting chains (monitor, scattered-beam point detector, fluorescence, drain-current / total-electron-yield). Is the point detector best a `FluxMonitor`, or does scattered-beam point-counting earn its own Sensor Family? | The scattered-beam point detector and the monitor / fluorescence / yield channels bind `FluxMonitor`; no detector Family invented. | The detector modelling. |

### i10-1 magnet endstation (i10-1)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MAG-1 | Blocks-go-live | The i10-1 electromagnet and superconducting field-sweep magnet (field ranges, the sweep mode), and the low-temperature environment. | The two magnets bind the graduated catalog `Magnet` Family (one Family, the sweep is a per-Asset affordance); i10-1 was one of its three consumers with 4-ID and ID32; the cryostat folds into the stage. | The per-Asset magnet field / control detail; the family graduation is settled (see [Model](#loose-families-at-a-second-sighting)). |

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
| TECH-1 | Blocks-go-live | Do the resonant-scattering, reflectivity, and magnetic-dichroism techniques (RSXS, soft X-ray reflectivity, XMCD, XMLD) enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices; resonant scattering and XMCD share the 4-ID Methods, XMLD shares the i06 slug, reflectivity is a new pending slug; none coined. | The technique Capabilities. |
