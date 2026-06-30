# Controls

*The energy-selecting turbo slit, the trajectory PMAC, the PandA timing, and the seam between CORA and the floor. These are the EDE periphery the commissioning module does model.*

## Selecting energy from the dispersed fan: the turbo slit

In full EDE the strip detector reads the whole energy band at once. The `TurboSlit` (`BL51P-OP-PCHRO-01:TS:`) is the device that, for alignment or single-energy work, picks one energy out of the polychromatic fan: its `xfine` axis is the main scanning axis (energy), `gap` sets the energy resolution, and `arc` is the coarse gap-centre. It reuses the `Slit` family; the `EnergyAxis` is its xfine selection. The bent-crystal polychromator that produces the fan it selects from is the open question POLY-1.

## The fly-scan: PMAC trajectory + PandA timing

The turbo-slit `xfine` axis is swept by a `TurboSlitController`, a PMAC trajectory controller (`BL51P-MO-STEP-06:`) running a trajectory program over its coordinate system, reused as a `MotionController`. Two PandA FPGA boxes (`Timing`, `BL51P-EA-PANDA-02:` and `-PANDA-01:`) provide the hardware triggering and position capture that synchronize the sweep with the detector, reused as a `TimingController`. This trajectory-plus-position-capture fly-scan is the same hardware-orchestration shape CORA drives at the other beamlines (the Zebra / PandA pattern), here applied to the energy-selecting slit.

## The seam: CORA and the floor

This is where CORA's design meets the I20-1 floor. The shape matches the other dodal-modelled Diamond beamlines'.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the EDE acquisition: arming the strip detector (when modelled), driving the turbo-slit / PMAC fly-scan for energy selection or alignment, and reading the detector through the time series;
- the choice of technique and timing, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd-async device layer (dodal): the turbo slit, the PMAC, the PandAs, the sample stage, the Xspress3, the `ControlPort` boundary;
- the polychromator crystal and the strip detector, once they are PV-bound (POLY-1 / STRIP-1);
- the facility filestore where the per-shot spectra land. CORA moves them, over the `TransferPort`, into CORA's own Dataset of record.

So CORA brings one conducting engine to I20-1, working over the ports: the EDE fly-scan over the `ControlPort`, the spectrum extraction (the dispersed-frame to absorption-spectrum reduction) over the `ComputePort`, and data egress over the `TransferPort`. The reduction is a clean `ComputePort` leg, the dispersive analogue of the reconstruction legs at the imaging beamlines.

The software interfaces (`PandA`, `PMAC`, `Xspress3`) are referenced by interface only, never registered as Assets.
