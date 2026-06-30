# Techniques

*What the modelled part of i06 is designed to do, as intent. Scaffold.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md#the-techniques-adapted-here) is how a facility adapts it. i06's techniques all sit in one family: polarization-driven dichroism. Every one of them turns the X-ray polarization at an absorption edge and reads the change in contrast, whether that contrast is an absorption spectrum, an electron image, or a diffraction peak. So i06's modelling story is not a new recipe over the spine; it is a new acquisition axis (the polarization) that the existing soft X-ray Methods now drive.

i06 is CORA's first APPLE-II source, so it is the first beamline that can set that axis at all. It is also CORA's first PEEM (photoemission electron microscopy) endstation, an electron-imaging technique whose defining instrument (the electron-optical column and its image detector) is not yet a CORA device (PEEM-1). The function view below survives both: it describes what each technique does, while the catalog vocabulary and the deferred instruments are carried as questions.

## The polarization-driven dichroism family

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

- **Two techniques reuse 4-ID Methods; two are new.** XMCD and resonant soft X-ray diffraction are the same Methods CORA already carries pending from the 4-ID POLAR deployment, so i06 is a second consumer rather than a coiner: the second consumer is the graduation watch-item for both. XMLD and photoemission microscopy have no existing Method that fits, so they are new pending slugs (`xmld`, `photoemission_microscopy`). Whether any of the four enters CORA's catalog as a Capability is an owner decision (TECH-1, PEEM-1).

- **PEEM is an imaging technique, and its instrument is not modelled yet.** PEEM is distinct from the electron-energy analysis of ARPES (the ESM endstation): ARPES analyses the energy and angle of photoelectrons, while PEEM forms a magnified spatial image of where they came from. The instrument that forms that image, the electron-optical column and its magnified electron-image detector, is absent from dodal and is deferred (PEEM-1). CORA models the PEEM sample manipulators now (they reuse the graduated `Manipulator` Family), and the column and image detector land once their PV handles are sourced. The `photoemission_microscopy` Method is the technique view of the same deferral: the recipe is named, the imaging instrument it would bind is not yet coined.

- **Resonant diffraction and XAS reuse the i06-1 geometry, and the detectors are deferred.** The i06-1 diffractometer (sample circles plus the detector arm) and the absorption stage are modelled now (DIFF-1, STAGE-1), but the i06-1 scattering detector and any incident-flux or drain-current electron-yield monitor are absent from dodal and are not invented (DET-1). So the techniques that read a diffraction peak or an absorption spectrum carry their detector as pending: the geometry that aims the beam is in the model, the device that records the signal is bound later.

## Polarization as a new operating axis for the fleet

The genuinely new thing i06 brings is not a Method; it is an axis. An APPLE-II undulator can drive its magnetic phase rows to choose the X-ray polarization, not just set a gap, so for the first time in the fleet a run can ask for a polarization the way it asks for an energy.

i06 models this as a [`PseudoAxis`](../../catalog/families.md), a sibling of the incident-energy pseudo-axis over the same source (the 2-BM beam-energy precedent, extended to a second driven source quantity). The shape is:

- **Set the polarization on the APPLE-II.** The axis's value domain is the polarization set the source can produce: linear horizontal (LH), linear vertical (LV), linear at an arbitrary angle (LA), circular positive (PC), circular negative (NC), plus third-harmonic variants (POL-1). The run names a value; CORA writes it; the source's phase rows move to produce it.

- **Flip or rotate it at an absorption edge to make the contrast.** XMCD flips between PC and NC at a magnetic edge and reads the absorption difference. XMLD rotates between two linear angles. Resonant diffraction tunes the polarization and the incident energy together through a resonance. In every case the contrast is the change the polarization causes, so turning the polarization at the edge is the acquisition primitive the whole dichroism family is built on.

- **The conversion stays on the live controller.** The polarization-to-phase kinematics (how a requested polarization becomes a phase-row position) is the axis's partition rule, and it is carried rule-less by default: the live i06 controller owns the conversion, so CORA names the axis and records the move without duplicating a second source of truth for the source geometry (POL-1). Pinning the conversion as a CORA-owned Calibration is deferred until a run needs to scan polarization without that controller in the loop. The same asymmetry the source-axis wiring carries (only the upstream IDU exposes the driven polarization handle in dodal) is an open question (POL-2).

This is the new acquisition primitive expressed entirely by reuse. The polarization axis is a `PseudoAxis` and the source is an `InsertionDevice`; no new device Family appears. What is new is that a run now carries a polarization alongside its energy, and the dichroism Methods drive both.

## Not modelled yet

The intent above is the function view. The concrete recipes that turn it into runnable acquisition are deliberately not written, because writing them for a beamline CORA does not yet drive would be invention rather than record:

- **The concrete dichroism recipes.** The per-edge energy and polarization sequences, the dwell and averaging, the field and temperature setpoints for an in-situ measurement, and the PEEM imaging sequence are calibration the deployment must supply. None of it is invented here.

- **Whether each Method enters the catalog.** Minting a Method is owner-scope. XMCD and resonant scattering reuse 4-ID Methods, and XMLD and photoemission microscopy are new slugs, but all four render pending until the owner decides (TECH-1, PEEM-1). The decision is recorded on the [Model](model.md) page, not made here.

- **The PEEM imaging instrument.** The PEEM electron-optical column and its magnified electron-image detector are deferred (PEEM-1): they are the `ElectronMicroscope` anatomy, distinct from the photon `Camera` and from the energy-analyzing catalog `ElectronAnalyzer`, and they are not coined here because they have no PV in dodal.

- **The i06-1 detectors and flux monitor.** The diffraction scattering detector and the incident-flux / drain-current monitor are absent from dodal and are bound later from outside it, with no detector Family invented in the meantime (DET-1).

For the source and optics that feed these techniques, see the generated source-walk on [the beamline page](beamline.md). For what the i06 team must confirm before the model can be trusted, see [Open questions](questions.md). The CORA-owned scope decisions (the polarization Calibration, the deferred Methods, the diffractometer Assembly) are recorded on the [Model](model.md#deliberately-not-here-yet) page.
