# Controls

*The software-triggered acquisition, the motion controllers, and the seam between CORA and the floor.*

## Triggering: software-gated acquisition

XPD does not use a hardware position-capture box. Its area detectors run in continuous or multi-trigger mode, gated by the endstation exposure shutter (`ExposureShutter`, `XF:28IDC-ES:1{Sh:Exp}`); a fast rapid-acquisition PDF measurement is a burst of detector frames over a held exposure. The exact acquisition modes are part of the recipe layer (deferred at this design phase).

## Motion controllers

The diffractometer, sample, and detector stages are driven by endstation and optics motion controllers whose box models, firmware, and IPs are not in the profile collection (DRIVE-1), so `EndstationMotionController` is carried as a `MotionController` family with the specifics blank.

## The seam: CORA and the floor

This is where CORA's design meets the XPD floor. The shape matches the other NSLS-II beamlines'.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the acquisition: stepping or ramping the sample environment, positioning the detector distance, and collecting the flat-panel frames under the gated exposure;
- the choice of technique, detector, distance, and sample-environment program, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd hardware abstraction: the `ControlPort` boundary;
- the double-Laue and high-resolution mono drives, the mirror bender, the cryostream / furnace controllers, the PSS interlock, and the detector IOCs;
- the facility filestore where the per-run frames land. CORA moves them, over the `TransferPort`, into CORA's own Dataset of record.

So CORA brings one conducting engine to XPD, working over the ports: powder / PDF acquisition over the `ControlPort`, the azimuthal integration and pair-distribution-function reduction over the `ComputePort`, and data egress over the `TransferPort` into the CORA Dataset. The integration and PDF reduction are a clean `ComputePort` leg, the powder-diffraction analogue of the reconstruction legs at the imaging beamlines.

The software IOCs (`PerkinElmer`, `Dexela`, `QuadEM`, `Cryostream`, `Lakeshore`, `Linkam`, the sample robot) are referenced by PV namespace only, never registered as Assets.
