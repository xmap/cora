# Techniques

*What Bernina is designed to do, as design intent. Design-phase: these are Methods CORA would earn, not Methods it has.*

Bernina runs two technique families, neither of which fits the catalog's tomography Methods, so each is carried pending on the [PSI Practices](../psi/index.md) until it is earned. They are listed here as design intent, with the shape each would take over the spine and the gap each leans on.

## Femtosecond optical pump-probe

The shared SwissFEL technique, the same one [Alvra](../alvra/techniques.md) and [LCLS-MFX](../lcls-mfx/techniques.md) run. An optical laser pulse excites the sample a controlled femtoseconds before (or after) the X-ray probe pulse; scanning the delay resolves the dynamics in time. The PSEN spectral-encoding arrival-time monitor corrects the residual laser-to-X-ray jitter shot by shot.

- **Spine shape:** a `pump_probe` Method that scans the laser-to-X-ray delay (a `LinearStage` delay axis on the experiment laser) while acquiring per-shot, with the PSEN monitor correcting jitter.
- **Gap it leans on:** the cross-timing-domain synchronization (LASER-1). The delay axis itself is a positioner; what CORA cannot express is the femtosecond synchronization between the optical-laser and FEL timing domains (the `eco` `lxt` timing chain). Bernina is the third deployment to reach this gap (after LCLS-MFX and Alvra).

## Time-resolved hard X-ray diffraction and scattering

Bernina's reason for existing, and what distinguishes it from Alvra. After the pump, the sample's structural response is read by diffraction: Bragg peaks and diffuse scattering recorded shot by shot on the area detector, as a function of pump-probe delay. The sample is oriented and the detector positioned by the GPS six-circle or XRD You-geometry diffractometer.

- **Spine shape:** a `diffraction` Method binding the diffractometer (a `Goniometer` for the sample circles, a `RotaryStage` 2-theta detector arm, and a reciprocal-space `PseudoAxis`), composed through the graduated `Diffractometer` Assembly (DIFF-1), over a per-shot acquisition. The reciprocal-space layer resolves the hkl inverse kinematics, and for the XRD platform the kappa-to-Eulerian conversion (DIFF-2).
- **Gap it leans on:** the per-shot, pulse-ID-tagged event DAQ (DAQ-1). A time-resolved diffraction run is a free-running shot stream tagged by pulse-ID and delay, not a trajectory of points the spine walks. The diffractometer itself is fully covered by the existing Assembly; the acquisition is the gap.

## Why neither is in the catalog yet

The catalog's Methods are all tomography-family (`tomography`, `dark_field`, `flat_field`, the alignment and energy-change methods). An XFEL diffraction station shares none of them: there is no rotation tomography, no flat / dark frame pairing, no storage-ring energy ramp. The `diffraction` Method is genuinely new for the fleet (the synchrotron diffractometers at 4-ID and 8-ID carry their own pending Methods), and coining it now, before the per-shot acquisition axis it depends on exists (DAQ-1), would be inventing a recipe for a spine that cannot yet run it. So it is carried pending. That a diffraction technique reaches the **same** acquisition gaps a spectroscopy technique (Alvra) and a crystallography technique (LCLS-MFX) reached is the reinforcement Bernina adds: the gaps are about the XFEL acquisition paradigm, not about any one technique. See [Model](model.md) for the gap register and the `Diffractometer` Assembly design.
