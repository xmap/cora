# Techniques

*What Cristallina is designed to do, as design intent. Design-phase: these are Methods CORA would earn, not Methods it has.*

Cristallina runs two technique families, neither of which fits the catalog's tomography Methods, so each is carried pending on the [PSI Practices](../psi/index.md) until it is earned. They are listed here as design intent, with the shape each would take over the spine and the gap each leans on.

## Time-resolved hard X-ray diffraction and scattering (quantum materials)

Cristallina's reason for existing. The Cristallina-Q endstation studies quantum materials: their structural and electronic response is read by diffraction and scattering, shot by shot, in a controlled low-temperature, high-magnetic-field environment. The sample is oriented and the detector positioned by the DM1 dilution-fridge or DM2 pulsed-magnet diffractometer, inside the DilSc dilution refrigerator and its vector superconducting magnet.

- **Spine shape:** a `diffraction` Method binding the diffractometer (a `Goniometer` for the sample circles, a `RotaryStage` 2-theta detector arm, and a reciprocal-space `PseudoAxis`), composed through the graduated `Diffractometer` Assembly (DIFF-1), over a per-shot acquisition, with the sample-environment state (temperature from the LakeShore 372, field from the vector magnet) as conditions. It shares the `diffraction` Method Bernina introduced.
- **Gap it leans on:** the per-shot, pulse-ID-tagged event DAQ (DAQ-1). A time-resolved diffraction run is a free-running shot stream tagged by pulse-ID, not a trajectory of points. The diffractometer is covered by the existing Assembly, and the sample environment by the `TemperatureController` Family and the loose `Magnet`; the acquisition is the gap.

The vector magnet is what distinguishes Cristallina-Q from Bernina's diffraction: the experiment sweeps not just delay and orientation but a three-axis magnetic field, in a dilution-fridge temperature regime. That sample environment is modelled (the LakeShore as `TemperatureController`, the magnet as the loose `Magnet`, the fourth consumer held at the rule-of-three, MAG-1) and gated by a Clearance hazard, but it adds no new technique-modelling shape beyond the conditions a Run already carries.

## Serial femtosecond crystallography

The Cristallina-MX endstation runs serial crystallography: microcrystals are delivered onto the fast XY sample stage and each X-ray pulse records a single-shot diffraction pattern. It shares the `serial_crystallography` Method LCLS-MFX and Alvra carry.

- **Spine shape:** a `serial_crystallography` Method binding the fast sample stage, the focusing optics, and the 8M Jungfrau, over a free-running per-shot acquisition.
- **Gap it leans on:** the per-shot, pulse-ID-tagged event DAQ (DAQ-1), the same as for the other XFEL serial-crystallography exercises. The sample delivery beyond the fast stage is endstation-specific and deferred (SAMPLE-1).

## Why neither is in the catalog yet

The catalog's Methods are all tomography-family. An XFEL diffraction / crystallography station shares none of them, and coining XFEL Methods now, before the per-shot acquisition axis they depend on exists (DAQ-1), would be inventing recipes for a spine that cannot yet run them. So each is carried pending, reusing the Method name Bernina or LCLS-MFX named for it. That a third PSI station, on a different controls library (`slic`) and with a novel sample environment (the vector magnet), reaches the same acquisition gaps is the reinforcement Cristallina adds: the gaps are about the XFEL acquisition paradigm, not the technique or the controls house style. See [Model](model.md) for the gap register, the `Diffractometer` Assembly design, and the `Magnet` rule-of-three.
