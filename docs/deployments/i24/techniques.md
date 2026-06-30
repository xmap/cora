# Techniques

*What i24 is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md) is how a facility adapts it. i24 is the first serial / fixed-target macromolecular-crystallography beamline CORA has looked at, so its technique is a new acquisition shape over the spine, not a recipe over Methods that already exist. Whether it enters the catalog as a Capability is an open question (SSX-1); the function view below survives the eventual vocabulary choice.

| Technique | Beam | Detector | Status in CORA |
| --- | --- | --- | --- |
| Fixed-target serial crystallography | monochromatic, focused | `Eiger` (Detector Role) | a new `serial_crystallography` Capability binding the chip stage + Eiger + sample shutter + Zebra, deferred (SSX-1) |
| Chip raster fly-collection | monochromatic, focused | `Eiger` + `OnAxisViewer` | the acquisition primitive of the technique above: window-addressed, Zebra-gated, no rotation (SSX-1, CHIP-1) |
| Pump-probe excitation | monochromatic, focused | `Eiger` | PMAC-fired lasers on encoder edges; modelled as a trigger setting or a hazard, deferred (LASER-1) |
| Jungfrau commissioning collection | monochromatic, focused | `Jungfrau` (Detector Role) | the same shape on the commissioning detector; carried pending (DET-1) |

A few points of intent shape the model:

- **Serial collection is a new acquisition shape, not a new device.** Rotation MX at I03 sweeps the goniometer omega while the Eiger captures frames through a continuous oscillation: one crystal, one trajectory of angles. i24 does the opposite. The chip stage rasters a fixed-target chip of thousands of static crystals across the beam, and the detector takes one diffraction snapshot per addressable window, with no goniometer rotation at all. The dataset is many single-orientation patterns, indexed and merged downstream, rather than one rotation sweep. The device Roles already exist (the chip stage presents Positioner, the Eiger presents Detector, the Zebra presents the timing surface); what is new is the recipe that binds them as a window-by-window fly-collection.

- **The catalog has no Method that fits, so i24 earns a Capability.** The tomography Methods bind RotaryStage + Camera + Scintillator over a rotation trajectory, and the I03 rotation MX Methods are a continuous omega sweep over a single crystal; neither matches a triggered raster over a grid of static samples. So serial crystallography is a new `serial_crystallography` Capability rather than a Method under an existing one. Whether it enters CORA's catalog is an owner decision, so the Practice renders pending (SSX-1). i24 is the first synchrotron consumer; the SLAC LCLS-MFX XFEL deployment already carries the same Method pending, so the second consumer is the graduation watch-item.

- **The chip raster is hardware-sequenced, and that sequencing is the seam CORA's edge replaces.** The serial trajectory (set a window, gate the exposure, step to the next) runs on the PMAC motion controller, with the Zebra FPGA TTL-gating the detector and the fast sample shutter per window off encoder position-compare. CORA does not model the PMAC motion program or the Zebra trigger graph as devices; it drives them through EPICS as the orchestration the edge conducts. The detailed raster pattern, the per-window dwell, and the trigger timing are calibration the deployment must supply (SSX-1).

- **The fixed-target chip is a Fixture and a Subject grid, not a PV.** The chip itself is the addressable holder the stage rasters one window at a time, and the crystals it carries are Subjects. The chip stage is a `LinearStage` Asset, but the grid geometry and the well / aperture map live in beamline software, not on a PV, so the chip-as-Fixture and the Subject grid are deferred as a CORA modelling decision (CHIP-1). Whether the chip windows are Subjects in a custody grid is the load-bearing question for the serial Subject thread.

- **There is no sample-exchange loop to model.** Rotation MX at I03 leans on an autonomous robot that loads pins one crystal at a time, which becomes a Procedure plus a Subject custody thread. i24 has no robot and no per-crystal exchange: one chip carries thousands of crystals, loaded once and rastered as a unit. The custody thread is over the chip and its grid, not over a stream of mounted pins.

The concrete recipe (the raster pattern, the per-window dwell, the laser and Zebra trigger timing, the chip grid map) is calibration the deployment must supply. See [Open questions](questions.md) for what must be confirmed first.
