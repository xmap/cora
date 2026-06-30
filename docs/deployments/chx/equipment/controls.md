# Controls

*The Zebra trigger that gates an XPCS time series, the motion controllers, and the seam between CORA and the floor.*

## Triggering: the Zebra and the fast shutter

An XPCS measurement is a long, fast train of detector frames under a precisely gated exposure. CHX uses a Zebra FPGA box (`Zebra`, `XF:11IDB-ES{Zebra}:`) to gate the fast shutter (`OUT1_TTL` / `SOFT_IN`) and the Eiger frame triggers, with a soft-IOC delay generator (`delaygen:DG0:`) and a fast shutter on the `Pel-IO` digital-output line alongside. The exact co-timing of the three, and the vendor identities, are a staff question (TIMING-1). This is the same hardware-gated-exposure role the Zebra plays at the other NSLS-II beamlines, here timing a coherent time series rather than a position raster.

## Motion controllers

The sample and optics axes are driven by endstation motion controllers whose box models, firmware, and IPs are not in the profile collection (DRIVE-1), so `EndstationMotionController` is carried as a `MotionController` family with the specifics blank.

## The seam: CORA and the floor

This is where CORA's design meets the CHX floor. The shape matches the other NSLS-II beamlines'.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the XPCS acquisition: arming the Eiger for a long frame series, gating the exposure through the Zebra and fast shutter, and the static SAXS/WAXS and GISAXS acquisitions on the same detectors;
- the choice of technique, detector, and exposure, gated by the [trust boundary](../governance.md#the-trust-boundary).

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd hardware abstraction: the `ControlPort` boundary;
- the Zebra gating, the delay generator and fast shutter, the DCM / DMM drives, the mirror and transfocator feedback, the PSS interlock, and the Eiger / Xspress3 detector IOCs;
- the facility filestore where the per-run frames land. CORA moves them, over the `TransferPort`, into CORA's own Dataset of record.

So CORA brings one conducting engine to CHX, working over the ports: XPCS / scattering orchestration over the `ControlPort`, the correlation analysis (the g2 / multi-tau computation) over the `ComputePort`, and data egress over the `TransferPort` into the CORA Dataset. The correlation analysis is a clean `ComputePort` leg, the coherent-scattering analogue of the reconstruction legs at the imaging beamlines.

The software IOCs (`Eiger`, `Xspress3`, `Zebra`, `Prosilica`, `Scaler`, `Linkam`, the delay generator) are referenced by PV namespace only, never registered as Assets.
