# Controls

*The Zebra position-capture trigger, the motion controllers, and the seam between CORA and the floor.*

## Triggering: the Zebra

SRX uses a Zebra FPGA position-capture box (`Zebra1`, `XF:05IDD-ES:1{Dev:Zebra1}:`) to hardware-gate the per-point detector triggers during a fly XRF raster, the same position-compare role at FXI (Aerotech PSO), HXN, and 2-BM. A second `Zebra2` is also present (ZEBRA-1).

## Motion controllers

The nano-stage and KB motion controllers drive the raster and focusing axes. Their box models, firmware, and IPs are not in the profile collection (DRIVE-1), so `EndstationMotionController` is carried as a `MotionController` family with the specifics blank.

## The seam: CORA and the floor

This is where CORA's design meets the SRX floor. The shape matches the other NSLS-II beamlines'.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the scan orchestration: the fly XRF raster (and the XANES energy sweep, and the XRF-tomography raster x rotation), hardware-gated per point by the Zebra, reading the technique's detector(s).
- the choice of which technique/detector to run, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd hardware abstraction: the `ControlPort` boundary;
- the Zebra position-compare gating, the HDCM Bragg drive and feedback, the KB and nano-stage closed-loop feedback (FPS / PICOSCALE interferometers), the PSS/PPS interlock, and the detector IOCs;
- the facility filestore where the per-scan data lands. CORA moves it, over the `TransferPort`, into CORA's own Dataset of record.

So CORA brings one conducting engine to SRX, working over the ports: scan orchestration over the `ControlPort`, any reconstruction/fitting (XRF fitting, ptychography, tomography) over the `ComputePort`, and data egress over the `TransferPort` into the CORA Dataset.

The software IOCs (`Xspress3`, `Merlin`, `Dexela`, `Eiger`, `PCO`, `Zebra`, `Struck`, `Qmini`) are referenced by PV namespace only, never registered as Assets.
