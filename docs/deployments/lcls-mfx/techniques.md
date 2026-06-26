# Techniques

*What MFX is designed to do, as design intent. Design-phase: these are Methods CORA would earn, not Methods it has.*

MFX runs three technique families, none of which fits the catalog's tomography Methods, so each is carried pending on the [SLAC Practices](../slac/index.md) until it is earned. They are listed here as design intent, with the shape each would take over the spine and the gap each leans on.

## Serial femtosecond crystallography (SFX)

A stream of microcrystals is delivered into the focused FEL beam (liquid jet or fixed target); each X-ray pulse destroys its crystal but records a diffraction pattern first ("diffraction before destruction"). The dataset is millions of single-shot patterns, indexed and merged downstream.

- **Spine shape:** a `serial_crystallography` Method binding the focusing lenses, the sample delivery, the pulse picker, and the area detector, over a Run that is a free-running per-shot acquisition rather than a trajectory of points.
- **Gap it leans on:** the per-shot, pulse-ID-tagged event DAQ (DAQ-1). This is the technique that most exposes the acquisition-ontology gap: there is no trajectory to walk, only a shot stream to tag and reference.

## Femtosecond optical pump-probe

An optical laser pulse excites the sample a controlled femtoseconds before (or after) the X-ray probe pulse; scanning the delay resolves dynamics in time.

- **Spine shape:** a `pump_probe` Method that scans the laser-to-X-ray delay (a `LinearStage` delay axis) while acquiring per-shot, with the timetool correcting residual jitter shot by shot.
- **Gap it leans on:** the cross-timing-domain synchronization (LASER-1). The delay axis itself is a positioner; what CORA cannot express is the femtosecond synchronization between the optical-laser and FEL timing domains (the `lxt_ttc` SyncAxis).

## X-ray emission spectroscopy (XES / HERFD)

The von Hamos 6-crystal spectrometer disperses the X-ray fluorescence emitted by the sample onto a 2D detector, resolving emission energy; in HERFD mode the incident energy is scanned at a fixed emission line.

- **Spine shape:** an `xas_spectroscopy` Method binding the emission spectrometer and, for HERFD, the incident-energy choreography (the DCCM), over a per-shot acquisition.
- **Gap it leans on:** the emission spectrometer binds the `EmissionSpectrometer` family it introduced, since graduated once ISS earned the 2nd sighting (SPEC-1 now tracks only the analyzer-crystal composition), and HERFD's incident-energy scan reuses the energy-change choreography CORA already models well.

## Why none is in the catalog yet

The catalog's Methods are all tomography-family (`tomography`, `dark_field`, `flat_field`, the alignment and energy-change methods). An XFEL shares none of them: there is no rotation, no flat / dark frame pairing, no storage-ring energy ramp. Coining XFEL Methods now, before the acquisition axis they depend on exists, would be inventing recipes for a spine that cannot yet run them. So each is carried pending, naming the Method it would earn, and the deepest dependency (the event-stream acquisition axis, DAQ-1) is sketched as a design note rather than built. See [Model](model.md) for the gap register.
