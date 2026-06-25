# Controls

*The conducting engine that runs the energy scan, the motion controller, and the seam between CORA and the floor.*

## The energy scan

BMM's measurement is an energy sweep: step (or glide) the monochromator Bragg angle across an absorption edge, and read the ion chambers and fluorescence detector at each point. CORA's conducting engine owns that sweep, over the `ControlPort`: set the next energy, wait for the optic to settle, read the per-point detectors, advance. This is the energy-scan analog of HXN's position raster, and it is the first real consumer of the `energy_scan` Capability the catalog anticipates (see [Techniques](../techniques.md)).

## Motion controllers

| Asset | Family | Drives |
| --- | --- | --- |
| `EndstationMotionController` | MotionController | the XAFS sample table (`MC:09`) and endstation stages |

The controller PV (`MC:09`) is in source; its box model, firmware, and IP are not (DRIVE-1).

## The seam: CORA and the floor

This is where CORA's design meets the BMM floor. The shape matches FXI's and HXN's, with BMM's energy-scan twist.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the energy scan: sweeping the monochromator energy and reading I0/It/Ir and the fluorescence detector per point. CORA's engine runs this directly; it replaces the beamline's current scan orchestration.
- the batch loop over the sample wheel (index a sample, scan, advance), governed by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd hardware abstraction: the `ControlPort` boundary;
- the monochromator Bragg drive and feedback, the mirror benders, the PSS/PPS interlock, and the detector IOCs (quad electrometer, Xspress3);
- the facility filestore where the per-scan data lands. CORA moves it, over the `TransferPort`, into CORA's own Dataset of record.

So CORA brings one conducting engine to BMM, working over the ports: the energy scan and the wheel loop over the `ControlPort`, any EXAFS data reduction over the `ComputePort`, and data egress over the `TransferPort` into the CORA Dataset.

The software IOCs (`Xspress3`, `QuadEM`, `Struck`) are referenced by PV namespace only, never registered as Assets.
