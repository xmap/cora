# Techniques

*What I03 is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md) is how a facility adapts it. I03 is the first macromolecular-crystallography (MX) beamline CORA has looked at, so its techniques are new Methods over the spine. Which enter scope is an open question (TECH-1); the function view below survives the eventual vocabulary choices.

| Technique | Beam | Detector | Status in CORA |
| --- | --- | --- | --- |
| Rotation (oscillation) data collection | monochromatic, focused | `Eiger` (Detector Role) | new Method binding Goniometer + Eiger + SampleShutter, pending (TECH-1) |
| Grid scan / sample location | monochromatic, focused | `Eiger` + `OAV` | new Method over the Zebra/PandA fast grid scan, pending (TRIG-1, TECH-1) |
| Autonomous sample exchange | n/a | n/a | a Procedure over the spine + a Subject custody thread, pending (ROBOT-1) |
| Fluorescence / anomalous element ID | monochromatic | `FluorescenceDetector` (Sensor) | deferred until the detector is modelled (DET-1) |

A few points of intent shape the model:

- **MX data collection is a new Method, not a new Capability shape.** A rotation data collection sweeps the goniometer omega while the Eiger captures frames, gated by the fast sample shutter. The device Roles already exist (the graduated Goniometer presents Positioner, the Eiger presents Detector); what is new is the recipe binding them. The catalog tomography Methods do not fit (they bind RotaryStage + Camera + Scintillator, not Goniometer + Eiger), so MX earns its own Methods (TECH-1).
- **The autonomous loop is a Procedure plus Subject custody, not a device.** The unattended exchange (load pin, thaw, centre, collect, unmount, next) is the genuinely new and non-obvious part of MX automation. CORA expresses it as an orchestrated Procedure over the spine, threaded through the `Subject` aggregate (custody Received to mounted-on-goniometer to measured to Returned / Stored) and gated by a Clearance issued after a safety review. The robot itself is just a Positioner; the workflow is the modelling (ROBOT-1).
- **Energy change is a Method, not the dodal composite.** dodal couples the undulator and DCM through the `UndulatorDCM` composite, which owns no motors and is being retired upstream. CORA dissolves it into an `energy_change` Method binding the undulator gap and the DCM energy with the lookup-table perp/offset compensation (ENERGY-1).
- **Grid scan is a Method, not a device.** dodal exposes the fast grid scan only as devices (`ZebraFastGridScan`, `PandAFastGridScan`); CORA models the scan as a Method over the goniometer + detector driven by the timing hardware, not as an Asset (TRIG-1).

The concrete recipes (oscillation ranges, exposure, grid parameters, the exchange sequence) are calibration the deployment must supply. See [Open questions](questions.md) for what must be confirmed first.
