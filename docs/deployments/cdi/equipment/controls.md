# Controls

*The motion controllers, the timing gap, and the seam between CORA and the floor.*

## Triggering: a gap in the source

A coherent-imaging measurement is a gated exposure, often one synchronized with a scan: a ptychographic map steps the sample and takes a frame at each point, a Bragg-CDI series rocks the goniometer and takes a frame at each angle. At the other NSLS-II coherent and scanning beamlines a Zebra or PandA box gates the detector frames against the motion. The CDI profile collection, as read, exposes **no such trigger box**: there is no Zebra or PandA startup file, and no shutter PVs. The `EigerDetector` and `MerlinDetector` carry internal and external trigger modes in their device classes, but how an exposure is gated and synchronized with the scan on the floor is not in source. This is the headline controls question (TIMING-1): it is carried as a deferral, modelled by what is real (the detector trigger modes), not invented.

## Motion controllers

The optics, KB, goniometer, and tower axes are EPICS motor records whose controller boxes, firmware, and IPs are not in the profile collection (DRIVE-1), so `EndstationMotionController` is carried as a single `MotionController` family with the specifics blank.

## The seam: CORA and the floor

This is where CORA's design meets the CDI floor. The shape matches the other NSLS-II beamlines'.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the coherent-imaging acquisition: aligning the KB nanofocus, setting the incident energy, positioning the sample on the goniometer, and arming the area detector for a forward-CDI frame, a ptychographic scan, or a Bragg-CDI rocking series;
- the choice of technique, detector, scan grid, and exposure, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd hardware abstraction: the `ControlPort` boundary;
- the DCM / DMM drives, the mirror and KB axes, the goniometer and tower motion, the PSS interlock, and the Eiger2 / Merlin detector IOCs;
- the facility filestore where the per-run frames land. CORA moves them, over the `TransferPort`, into CORA's own Dataset of record.

So CORA brings one conducting engine to CDI, working over the ports: coherent-imaging orchestration over the `ControlPort`, the phase retrieval and ptychographic reconstruction over the `ComputePort`, and data egress over the `TransferPort` into the CORA Dataset. The reconstruction is a clean `ComputePort` leg, the imaging analogue of the correlation analysis at [CHX](../../chx/equipment/controls.md#the-seam-cora-and-the-floor) and the reconstruction legs at the tomography beamlines.

The software IOCs (`Eiger`, `Merlin`, `Prosilica`, the `TetrAMM` and `i400` / `i404` electrometers, the `TDMS` tower IOC) are referenced by PV namespace only, never registered as Assets.
