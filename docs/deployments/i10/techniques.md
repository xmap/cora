# Techniques

*What the modelled part of i10 is designed to do, as intent. Scaffold.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md#the-techniques-adapted-here) is how a facility adapts it. i10 (BLADE) is i06's soft X-ray twin: the fleet's second APPLE-II source, sharing the twin-APPLE-II and PGM spine, feeding two endstations that study magnetic materials. Its techniques sit in the same family i06 already named, polarization-driven contrast, but i10 reads that contrast two ways i06 does not: it resolves the polarization of the scattered beam (the RASOR analyzer arm), and it makes the contrast under an applied magnetic field at low temperature (the i10-1 magnets).

So i10's modelling story is mostly reuse. The polarization acquisition axis already exists from i06, and three of i10's four Methods are already pending in CORA's catalog. What i10 adds on top is two affordances, polarization analysis and applied-field dichroism, expressed against families CORA already carries rather than new recipes over the spine. The function view below describes what each technique does, while the catalog vocabulary and the deferred decisions are carried as questions.

## The four techniques

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

- **Three techniques reuse existing Methods; one is new.** Resonant scattering and XMCD are the same Methods CORA already carries pending from the 4-ID deployment, and XMLD reuses the i06 slug, so for those three i10 is a second (or third) consumer rather than a coiner: the second consumer is the graduation watch-item. Reflectivity has no existing Method that fits, so it is a new pending slug. Whether any of the four enters CORA's catalog as a Capability is an owner decision (TECH-1), recorded on the [Model](model.md) page, not made here.

- **Resonant scattering and reflectivity reuse the RASOR geometry, and the science detector is a flux monitor.** The RASOR diffractometer (the two-theta scattering arm with sample theta, chi, chamber X, and alpha) is modelled now as a `Goniometer` (DIFF-1), with a reciprocal-space `PseudoAxis` over it (DIFF-2). There is no area detector at RASOR, so the scattered-beam point detector, the incident-flux monitor, the fluorescence channel, and the drain-current / total-electron-yield channel all bind the catalog `FluxMonitor` family through their current amplifiers (DET-1). The geometry that aims and reads the beam is in the model; the recipe that sequences a scan or a reflectivity curve is calibration the deployment supplies later.

- **XMCD and XMLD here are field-and-temperature techniques.** At i10-1 the contrast is made not just by turning the polarization but by applying a magnetic field with the sample held cold. The magnets are modelled (MAG-1), the cryostat stage and its temperature controller are modelled (TEMP-1), and the i10-1 point detection is again a `FluxMonitor` (DET-1). The applied-field affordance is what distinguishes i10's XMCD / XMLD from i06's, and it is the second of the two things i10 adds (see below).

## The polarization axis, reused from i06

The polarization acquisition axis is not new with i10. i06 brought it to the fleet first: an APPLE-II undulator drives its magnetic phase rows to choose the X-ray polarization, not just set a gap, so a run can ask for a polarization the way it asks for an energy. i10 is the fleet's second APPLE-II source and reuses that axis unchanged.

i10 models it as a [`PseudoAxis`](../../catalog/families.md) over the twin-APPLE-II phase rows, a sibling of the incident-energy pseudo-axis over the same source. The shape is:

- **Set the polarization on the APPLE-II.** The axis's value domain is the polarization set the source can produce: linear horizontal (LH), linear vertical (LV), circular positive (PC), circular negative (NC), and linear at an arbitrary angle (LA), plus third-harmonic variants (POL-1). The continuous linear-arbitrary-angle is the continuous realization of the LA value within this same axis, not a second axis and not a new family. The run names a value; CORA writes it; the source's phase rows move to produce it.

- **Turn it at an absorption edge to make the contrast.** XMCD flips between PC and NC at a magnetic edge and reads the absorption difference. XMLD rotates between two linear angles. Resonant scattering tunes the polarization and the incident energy together through a resonance. In every case the contrast is the change the polarization causes, so turning the polarization at the edge is the acquisition primitive the whole family is built on.

- **The conversion stays on the live controller.** The polarization-to-phase kinematics is carried rule-less by default: the live i10 controller owns the conversion, so CORA names the axis and records the move without duplicating a second source of truth for the source geometry (POL-1). Both undulators are driven sources, and whether the polarization handle is wired over one axis or two is an open question (ENERGY-1).

So far this is i06's primitive expressed by reuse: the polarization axis is a `PseudoAxis`, the source is an `InsertionDevice`, and no new device Family appears. i10 then adds two things i06 does not carry.

### What i10 adds: polarization analysis of the scattered beam

RASOR does not only set the incident polarization; it can resolve the polarization of the scattered beam. The motorized analyzer arm (the PaStage / POLAN arm, with its analyzer two-theta and theta, py and pz, and eta motors) selects a scattered-polarization channel, which is what lets resonant scattering separate the magnetic and charge contributions to a peak rather than read only its total intensity. This is the analysis half of polarization: i06 turns it, i10 also reads it back.

CORA models that arm as the loose `PolarizationAnalyzer` family. This is a deliberate modelling choice: dodal exposes only the arm's motors, and the analyzer crystal is implicit hardware, but RASOR's defining polarization-analysis role lives on that real motorized arm, so CORA models the arm rather than hiding the role. The analyzer crystal specifics are not invented (POL-2). This is the family's second sighting, after 4-ID, and it is held under review rather than graduated; the rule-of-three is not met, so i10 records HOLD and the graduate-or-hold call stays human (POL-2).

### What i10 adds: applied-field dichroism

The i10-1 / I10J endstation makes the dichroic contrast under an applied magnetic field, with the sample held at low temperature. Two magnet devices serve it: a set-and-read electromagnet and a superconducting magnet whose field can be swept (a Flyable affordance). CORA models both as the single loose `Magnet` family: they are one family, and the field sweep is a per-Asset affordance, not a split (MAG-1). This is the `Magnet` family's second sighting, after 4-ID, also held under review (MAG-1). The field values and the sweep specifics are not invented (MAG-1).

The applied field is what makes i10's XMCD / XMLD different from i06's: i06 reads dichroism from the polarization alone, while i10 reads it with a field applied and the sample cold. The cryostat low-temperature stage folds into the catalog `LinearStage`, and the magnet temperature is held by a catalog `TemperatureController` (TEMP-1). As with the polarization axis, no new device Family is coined for either addition: the analyzer is the loose `PolarizationAnalyzer`, the magnets are the loose `Magnet` family, and both are reuse held under review.

## Not modelled yet

The intent above is the function view. The concrete recipes that turn it into runnable acquisition are deliberately not written, because writing them for a beamline CORA does not yet drive would be invention rather than record:

- **The concrete recipes.** The per-edge energy and polarization sequences, the reflectivity angle and energy scans, the polarization-analysis channel selections, the field and temperature setpoints for an in-situ measurement, and the dwell and averaging are all calibration the deployment must supply. None of it is invented here. No energies, angles, fields, or resolutions are stated.

- **Whether each Method enters the catalog.** Minting a Method is owner-scope. Resonant scattering and XMCD reuse 4-ID Methods, XMLD reuses the i06 slug, and reflectivity is a new slug, but all four render pending until the owner decides (TECH-1). The decision is recorded on the [Model](model.md) page, not made here.

- **Whether the PolarizationAnalyzer and Magnet families graduate.** Both are loose families on their second sighting and held under review (POL-2, MAG-1). i10 records HOLD; the graduate-or-hold call is human and is not made here. The analyzer crystal and the magnet field values stay uninvented behind that hold.

- **The science detectors.** Neither endstation has an area detector. The RASOR and i10-1 point and current-integrating channels bind the catalog `FluxMonitor` through their current amplifiers (DET-1); no detector Family is invented in the meantime.

For the source and optics that feed these techniques, see the generated source-walk on [the beamline page](beamline.md). For what the i10 team must confirm before the model can be trusted, see [Open questions](questions.md). The CORA-owned scope decisions (the deferred Methods, the held families, the diffractometer Assembly) are recorded on the [Model](model.md#deliberately-not-here-yet) page.
