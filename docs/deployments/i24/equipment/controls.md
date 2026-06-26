# Controls

*The control stack and trigger scheme. Design-phase, with the dodal-derived handles recorded.*

i24 runs the Diamond EPICS control stack, the same floor as the other Diamond beamlines. As at I03, the control handles are **known**: Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) library records the real EPICS PV prefix for each device, so this scaffold carries `pv` on every device.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. For i24 the EPICS PV prefixes are recorded from dodal (`src/dodal/beamlines/i24.py` and its device classes), carried `confirm` because a controls-library snapshot is not a guarantee against the live system (CTRL-1). The PV naming follows the Diamond convention `BL<sector><branch>-<DOMAIN>-<TYPE>-<NN>:` (for example `BL24I-MO-VGON-01:` is beamline 24I, motion domain, vertical goniometer 01, and `BL24I-MO-CHIP-01:` is the fixed-target chip stage). The full handle list is in the [Inventory](../inventory.md).

What dodal does **not** give, and so is not invented: which access-gated hutch each device sits in (the PV encodes a functional zone, not a hutch or its PSS meaning, ENC-1), the PSS permit leaves behind the interlocked hutch shutter (PSS-1), and the calibrated values behind the handles.

## Timing and triggering

Timing is handled by one FPGA box, a Zebra (`BL24I-EA-ZEBRA-01:`), modelled as a `TimingController` device, the same Family the 2-BM Timing device and I22's and I03's FPGA boxes use. The Zebra fans out the TTL triggers and gates: it gates the per-window detector exposure (the Eiger, or the commissioning Jungfrau) and drives the fast sample shutter (`BL24I-EA-SHTR-01:`, dodal's MXZebraShutter).

What the Zebra hardware-sequences is the serial collection itself. Unlike I03 rotation MX, i24 takes no goniometer sweep: the chip stage (`BL24I-MO-CHIP-01:`, dodal's PMAC) rasters an addressable chip of thousands of static crystals across the beam, one diffraction snapshot per window, with the detector and fast shutter TTL-gated per window. The detailed trigger graph, the per-window dwell, and the PMAC laser triggers are the serial-collection seam CORA's edge drives, modelled as a Method over the chip stage plus detector rather than as Assets, and deferred pending the team (SSX-1, LASER-1).

## The floor: GDA, dodal, and the serial-collection seam

A seam observation, recorded for the eventual Conductor work: i24's acquisition floor is Diamond's GDA, with the device handles above bound from dodal. The serial collection runs as a hardware-sequenced motion program on the PMAC controller: the chip-raster trajectory, the encoder position-compare that fires each window, the laser triggers, and the Zebra TTL gating of the detector and fast shutter. That orchestration is what a future CORA edge replaces, driving through ophyd / EPICS, rather than the EPICS floor itself, which stays the floor.

Two surfaces stay plumbing CORA observes, not data it owns: the OAV zoom and beam-centre configuration, which lives in GDA files (dodal's OAVBeamCentreFile, the on-axis viewer `BL24I-DI-OAV-01:`, CTRL-1), and the detector file-writing to the Diamond filestore. These are control-system configuration and output, not CORA Assets, recorded because they are what the serial-collection seam reads and writes around.

See [Open questions](../questions.md) for the control and timing items still to confirm, and [Model](../model.md#deliberately-not-here-yet) for the serial-crystallography Capability and the fixed-target chip Fixture carried as deferred CORA decisions.
