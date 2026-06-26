# Controls

*The scaler-counted raster, the Maia fly-scan, the motion controller, and the seam between CORA and the floor.*

## Raster mapping

XFM acquires an XRF map by rastering the UTS stage while counting the detectors against the SIS3820 scaler. Two modes appear in the profile: a step grid (`bp.grid_scan` over the stage, counting the Xspress3 and the scaler per point) and a Maia continuous fly-scan (the stage moves continuously while the Maia array reads against its own encoder feedback). There is no separate hardware position-capture box in the profile collection; the scaler does the dwell / counting and the Maia handles its own fly timing.

## Motion control

The `StageMotionController` drives the UTS raster stage (and the optics axes); its box model, firmware, and IP are not in the profile collection (DRIVE-1), so it is carried as a `MotionController` family with the specifics blank.

## The seam: CORA and the floor

This is where CORA's design meets the XFM floor. The shape matches the other NSLS-II beamlines'.

CORA **owns** (its conducting engine, over the `ControlPort`):

- the acquisition: setting the energy, rastering the stage, and collecting the fluorescence detectors per pixel (step or Maia fly), with I0 normalization from the scaler;
- the choice of technique (XRF mapping, the XANES leg), gated by the [trust boundary](../governance.md#the-trust-boundary), and the energy / flux calibrations.

CORA **drives through** (the floor it actuates and observes, and does not replace):

- the EPICS IOCs via the ophyd hardware abstraction: the `ControlPort` boundary;
- the UTS stage, the Xspress3, the Maia array, and the SIS3820 scaler;
- the facility filestore where the per-map data lands. CORA moves it, over the `TransferPort`, into CORA's own Dataset of record.

So CORA brings one conducting engine to XFM, working over the ports: acquisition over the `ControlPort`, the per-map reduction (XRF spectrum fitting, element-map assembly) over the `ComputePort`, and data egress over the `TransferPort` into the CORA Dataset.

The software systems (`Xspress3`, the `Maia` system, the `SIS3820` scaler, the `nslsii` device library) are referenced by PV namespace only, never registered as Assets.
