# Controls

*The fast-shutter-gated acquisition, the motion controllers, and the seam between CORA and the floor.*

## Triggering: the fast shutter

SMI does not use a hardware position-capture box. Its Pilatus detectors run in software-triggered modes, gated by the endstation fast shutter (`FastShutter`, `XF:12IDC-ES:2{PSh:ES}`, a piezo open/close with a backing Y motor); a scattering measurement is a held exposure on both detectors at once. The exact acquisition modes are part of the recipe layer (deferred at this design phase).

## Motion controllers

The sample, detector, and beamstop axes are driven by endstation motion controllers (SmarAct MCS, MDrive, and Thorlabs units are named in source); their box models, firmware, and IPs are not fully in the profile collection (DRIVE-1), so `EndstationMotionController` is carried as a `MotionController` family with the specifics blank.

## The seam: CORA and the floor

This is where CORA's design meets the SMI floor. The shape matches the other NSLS-II beamlines'.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the acquisition: positioning the sample (including the grazing-incidence angle), setting the SAXS camera length and the WAXS arc, and collecting the two Pilatus frames under the gated exposure;
- the choice of technique, detectors, camera length, and in-situ environment program, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd hardware abstraction: the `ControlPort` boundary;
- the coupled energy pseudopositioner (undulator gap plus DCM), the mirror benders, the CRL transfocator, the WAXS-chamber vacuum automation, the PSS interlock, and the Pilatus detector IOCs;
- the facility filestore where the per-run frames land. CORA moves them, over the `TransferPort`, into CORA's own Dataset of record.

So CORA brings one conducting engine to SMI, working over the ports: scattering acquisition over the `ControlPort`, the azimuthal integration and reduction (the SAXS / WAXS / GISAXS data reduction) over the `ComputePort`, and data egress over the `TransferPort` into the CORA Dataset. The reduction is a clean `ComputePort` leg, the scattering analogue of the reconstruction legs at the imaging beamlines.

The software IOCs (`Pilatus`, `Amptek`, `TetrAMM`, `Prosilica`, `Linkam`, `LakeShore`, the SmarAct controllers, the blade coater) are referenced by PV namespace only, never registered as Assets.
