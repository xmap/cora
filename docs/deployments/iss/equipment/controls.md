# Controls

*The trajectory energy fly-scan, the synchronized readout, the motion controllers, and the seam between CORA and the floor.*

## The trajectory fly-scan

ISS's defining operation is a trajectory energy fly-scan. The high-heat-load monochromator energy axis (`XF:08IDA-OP{Mono:HHM-Ax:E}Mtr`) follows a pre-computed Bragg-angle look-up table loaded onto a Delta-Tau motion controller (`TrajectoryMotionController`, `XF:08IDA-OP{MC:06}`: load / transfer LUT, prepare / start / stop trajectory, progress, with per-element Traj:1-9 element / edge / E0 descriptors), while the detectors stream against an encoder pizza box. A measurement is one swept energy range, not a step-and-settle loop; CORA would model that sweep as conducting a Run, with the trajectory as a held setpoint program.

## Synchronized readout

The `AnalogPizzaBox` (APB, `XF:08IDB-CT{PBA:1}:`) is the synchronized multi-channel readout: an eight-channel ADC streaming the ion-chamber voltages plus a trigger / pulse generator timing the Xspress3 and the encoder against the energy sweep. It reuses the `TimingController` family. CORA reads its streamed channels as the per-scan data, correlated by the encoder position.

## Motion controllers

The remaining axes (mirrors, sample stages, slits, the emission-spectrometer crystals, the von Hamos `XF:08IDB-OP{MC:3-Ax:}` axes) are standard EPICS motor records; the controller box models, firmware, and IPs are not fully in the profile collection (DRIVE-1), so `TrajectoryMotionController` is carried as a `MotionController` family with the specifics blank.

## The seam: CORA and the floor

This is where CORA's design meets the ISS floor. The shape matches the other NSLS-II beamlines'.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the acquisition: loading and running the energy trajectory, positioning the sample, collecting the transmission / fluorescence channels, and driving the emission-spectrometer crystals for XES / HERFD under the synchronized readout;
- the choice of technique, energy range, detector, and in-situ environment program, gated by the [trust boundary](../governance.md#the-trust-boundary), and the per-scan energy calibration against the reference foil.

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd hardware abstraction: the `ControlPort` boundary;
- the Delta-Tau trajectory engine, the encoder / analog pizza box streaming, the mirror benders and feedback, the monochromator cooling, the PSS interlock, and the detector IOCs;
- the facility filestore where the per-run data lands. CORA moves it, over the `TransferPort`, into CORA's own Dataset of record.

So CORA brings one conducting engine to ISS, working over the ports: acquisition over the `ControlPort`, the per-technique reduction (EXAFS normalization and fitting, XES / HERFD spectra) over the `ComputePort`, and data egress over the `TransferPort` into the CORA Dataset.

The software IOCs (`Xspress3`, `Pilatus`, `Keithley428`, `Lakeshore331`, the analog pizza box, the trajectory manager, the Prosilica BPMs, Databroker) are referenced by PV namespace only, never registered as Assets.
