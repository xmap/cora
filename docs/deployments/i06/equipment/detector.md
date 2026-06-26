# Detector

*A deferred-detection first cut. i06's defining detectors, the i06-1 scattering detector and the i06-2 PEEM electron-image column, are absent from dodal, so this page models the detector-side geometry that is present and binds the actual detectors later. PVs read from dodal, carried confirm.*

i06 is two endstations with two very different detection shapes, and on both of them the device that actually records the signal is not in dodal yet. What dodal gives is the geometry around the detector: the i06-1 diffractometer carries a real detector arm and a reciprocal-space pseudo-axis over the circles, and the i06-2 branch carries the manipulators that move the sample in front of the PEEM column. The recording detectors themselves are absent. So this page models what is present, names what is missing, and coins no detector Family for hardware CORA cannot yet see. The geometry that is modelled lives in the detection and sample stages of the [descriptor](../inventory.md).

## i06-1 diffraction-dichroism detection (BL06J)

The i06-1 endstation is a soft X-ray diffractometer. dodal carries its mechanics, including the detector arm, but not the scattering detector that rides on that arm and not any incident-flux or drain-current monitor.

| Device | Family | Role | Control handle | Notes |
| --- | --- | --- | --- | --- |
| `Diffractometer` (detector arm) | `Goniometer` | Positioner | `BL06J-EA-DDIFF-01:DET:2THETA` / `:DET:Y` (DIFF-1) | the `DET:2THETA` / `DET:Y` detector arm, part of the sample-circle goniometer; positions where a detector would sit |
| `ReciprocalSpace` | `PseudoAxis` | Axis | over the i06-1 circles (DIFF-2) | reciprocal-space axis driving the circles to a reflection; sits over the diffractometer, not the detector |
| i06-1 scattering detector | (deferred) | Detector | absent from dodal (DET-1) | the device that records the scattered soft X-ray pattern; no PV in dodal, not invented here |
| incident-flux / drain-current monitor | (deferred) | (monitor) | absent from dodal (DET-1) | the I0 / electron-yield (drain-current) channel a dichroism measurement reads; absent from dodal, carried pending (DET-1) |

How this maps onto CORA:

- **The detector arm is goniometer geometry, not a detector.** The `DET:2THETA` / `DET:Y` motors are real and are part of the `Goniometer` Family the diffractometer binds (DIFF-1); they place a detector in the scattering plane. CORA models that arm now as the goniometer affordance it is. The detector that the arm carries is a separate Asset that does not exist in dodal, so it is held open (DET-1), not folded into the goniometer.
- **The reciprocal-space axis is over the circles, not the detector.** `ReciprocalSpace` reuses `PseudoAxis` and drives the sample circles to a reflection (DIFF-2). It is a sibling of the incident-energy and polarization pseudo-axes; it tells the mechanics where to point, and it does not stand in for the missing detector.
- **The dichroism signal is read against the polarization axis on the source side.** A magnetic-dichroism difference measurement subtracts signal taken at one polarization from signal taken at another. The detector and the flux / electron-yield monitor that produce that signal are the DET-1 deferral here; the axis they are differenced against is the FLEET-FIRST `Polarization` pseudo-axis over the APPLE-II, modelled on the source side (see [Beamline source walk](../beamline.md)).

## i06-2 PEEM detection (BL06K)

The i06-2 endstation is a photoemission electron microscope. The defining instrument is the electron-optical column that magnifies the emitted-electron image and the detector that records that magnified image. Neither is in dodal. dodal carries only the UHV manipulator and the energy-slit translation that position the sample in front of that column.

| Device | Family | Role | Control handle | Notes |
| --- | --- | --- | --- | --- |
| `PeemManipulator` | `Manipulator` | Positioner | `BL06K-MO-PEEM-01:` (MANIP-1) | UHV manipulator x / y / phi + the energy-slit translation; reuses the graduated `Manipulator` Family |
| `PeemSampleStage` | `Manipulator` | Positioner | `BL06I-MO-PEEM-01:` (MANIP-1) | the i06-branch PEEM sample stage x / y / phi; reuses `Manipulator` |
| PEEM electron-optical column | (deferred) | (electron-imaging optics) | absent from dodal (PEEM-1) | the magnifying electron-optical column; the `ElectronMicroscope` anatomy, not coined here |
| PEEM electron-image detector | (deferred) | Detector | absent from dodal (PEEM-1) | the detector that records the magnified electron image; absent from dodal, deferred (PEEM-1) |

How this maps onto CORA:

- **The manipulators are positioners, and they are all dodal gives the PEEM branch.** Both the UHV manipulator and the i06-branch sample stage reuse the `Manipulator` Family graduated across SIX and ESM (MANIP-1). They move the sample into the field of view; they are not the microscope.
- **The PEEM column and its image detector are the `ElectronMicroscope` anatomy, deferred.** A PEEM column is an electron-imaging instrument: it forms a magnified image from the electrons leaving the sample, and a detector records that image. That anatomy is distinct from a photon `Camera` (which images photons, not electrons) and distinct from the energy-analyzing catalog `ElectronAnalyzer` of ARPES (which disperses electrons by kinetic energy rather than imaging them). It is the loose `ElectronMicroscope` shape, the same deferral the ESM XPEEM/LEEM branch carries. Because no PV for the column or the image detector is in dodal, it is named as the deferral PEEM-1 and is NOT coined in this cut.

## Why no detector Family is coined

This page binds no detector Family, and that is a deliberate deferral rather than a gap to paper over.

- **The recording detectors are absent from dodal.** The i06-1 scattering detector, the i06-1 flux / electron-yield monitor (DET-1), and the i06-2 PEEM column and electron-image detector (PEEM-1) have no PVs in the dodal factories CORA reverse-engineers. CORA models geometry it can see and binds detectors when their handles appear.
- **No orphan Family.** Coining a Family for hardware that has no PV, no settings, and no Asset to attach to would leave an orphan in the catalog. The `ElectronMicroscope` anatomy that PEEM needs is the right eventual home (PEEM-1), but it is earned when a real column and image detector arrive, not declared against an absence. The catalog is unchanged by this deployment, and nothing graduates here.
- **The geometry that IS present is modelled now.** The detector arm rides the `Goniometer` (DIFF-1), the reciprocal-space axis reuses `PseudoAxis` (DIFF-2), and the PEEM manipulators reuse `Manipulator` (MANIP-1). Detector binding is the follow-on, taken up when CORA approaches driving i06 and the device handles are confirmed.

## Families

No new detector Family is earned. Reused from the catalog: `Goniometer` for the diffractometer and its detector arm (DIFF-1), `PseudoAxis` for the reciprocal-space axis (DIFF-2), `Manipulator` for the two PEEM stages (MANIP-1). Deferred, not coined: the i06-1 scattering detector and flux / electron-yield monitor (DET-1), and the i06-2 PEEM electron-optical column and electron-image detector, the loose `ElectronMicroscope` anatomy (PEEM-1). See [Inventory](../inventory.md) for the Asset tree, [Model](../model.md) for the modelling decisions, [Beamline source walk](../beamline.md) for the polarization axis the dichroism signal is read against, [Open questions](../questions.md) for the detector handles still to confirm, and the [Family catalog](../../../catalog/families.md) for the shared definitions.
