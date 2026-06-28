# Techniques

*What Alvra is designed to do, as design intent. Design-phase: these are Methods CORA would earn, not Methods it has.*

Alvra runs three technique families, none of which fits the catalog's tomography Methods, so each is carried pending on the [PSI Practices](../psi/index.md) until it is earned. They reuse the same pending Methods CORA's first XFEL, [LCLS-MFX](../lcls-mfx/techniques.md), introduced; Alvra is the second deployment to need them, which is part of the point. They are listed here as design intent, with the shape each would take over the spine and the gap each leans on.

## Femtosecond optical pump-probe

Alvra's reason for existing. An optical laser pulse excites the sample a controlled femtoseconds before (or after) the X-ray probe pulse; scanning the delay resolves the dynamics in time. The PALM (THz-streaking) and PSEN (spectral-encoding) arrival-time monitors correct the residual laser-to-X-ray jitter shot by shot.

- **Spine shape:** a `pump_probe` Method that scans the laser-to-X-ray delay (a `LinearStage` delay axis on the experiment laser) while acquiring per-shot, with the PSEN / PALM monitors correcting jitter.
- **Gap it leans on:** the cross-timing-domain synchronization (LASER-1). The delay axis itself is a positioner; what CORA cannot express is the femtosecond synchronization between the optical-laser and FEL timing domains (the `eco` `lxt` timing chain). This is the same gap LCLS-MFX's `lxt_ttc` SyncAxis exposed, now seen at a second XFEL.

## Time-resolved X-ray absorption and emission (XAS / XES / HERFD)

Alvra measures how a sample's electronic structure evolves after the pump: transient X-ray absorption through the incident energy (the double-crystal mono), and X-ray emission through the von Hamos spectrometer. In HERFD mode the incident energy is scanned at a fixed emission line.

- **Spine shape:** an `xas_spectroscopy` Method binding the `Monochromator` for the incident-energy choreography and the `EmissionSpectrometer` for the emitted spectrum, over a per-shot acquisition.
- **Gap it leans on:** the von Hamos binds the graduated `EmissionSpectrometer` Family (Alvra is a fourth sighting; SPEC-1 now tracks only the analyzer-crystal composition), and the HERFD incident-energy scan reuses the energy-change choreography CORA already models well. The time-resolution makes the acquisition per-shot, which leans on the DAQ gap (DAQ-1).

## Serial femtosecond crystallography (SFX)

On the Prime endstation Alvra also runs time-resolved serial crystallography: a stream of microcrystals is delivered into the focused FEL beam; each pulse records a single-shot diffraction pattern before destroying its crystal. The dataset is many single-shot patterns, indexed and merged downstream.

- **Spine shape:** a `serial_crystallography` Method binding the KB focusing, the sample delivery, the pulse picker, and the Jungfrau detector, over a Run that is a free-running per-shot acquisition rather than a trajectory of points.
- **Gap it leans on:** the per-shot, pulse-ID-tagged event DAQ (DAQ-1). As at LCLS-MFX, this is the technique that most exposes the acquisition-ontology gap: there is no trajectory to walk, only a shot stream to tag and reference.

## Why none is in the catalog yet

The catalog's Methods are all tomography-family (`tomography`, `dark_field`, `flat_field`, the alignment and energy-change methods). An XFEL pump-probe station shares none of them: there is no rotation, no flat / dark frame pairing, no storage-ring energy ramp. Coining XFEL Methods now, before the acquisition axis they depend on exists, would be inventing recipes for a spine that cannot yet run them. So each is carried pending, reusing the Method name LCLS-MFX named for it, and the deepest dependency (the event-stream acquisition axis, DAQ-1) is sketched as a design note rather than built. That the same three Methods are now needed at a second, independently-built XFEL is the strongest argument yet that they are real Methods to earn, not LCLS-specific. See [Model](model.md) for the gap register.
