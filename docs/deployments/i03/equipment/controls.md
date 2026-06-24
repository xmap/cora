# Controls

*The control stack and trigger scheme. Design-phase, with the dodal-derived handles recorded.*

I03 runs the Diamond EPICS control stack. As at I22, the control handles are **known**: Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) library records the real EPICS PV prefix for each device, so this scaffold carries `pv` on every device.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. For I03 the EPICS PV prefixes are recorded from dodal (`src/dodal/beamlines/i03.py` and its device classes), carried `confirm` because a controls-library snapshot is not a guarantee against the live system. The PV naming follows the Diamond convention `BL<sector><branch>-<DOMAIN>-<TYPE>-<NN>:` (for example `BL03I-MO-SGON-01:` is beamline 03I, motion domain, sample goniometer 01); the undulator uses the `SR03I` storage-ring root. The full handle list is in the [Inventory](../inventory.md).

What dodal does **not** give, and so is not invented: which access-gated hutch each device sits in (the PV encodes a functional zone, not a hutch or its PSS meaning, ENC-1), and the calibrated values behind the handles.

## Timing and triggering

Timing is handled by two FPGA boxes, the standard Diamond MX pairing:

- **A Zebra** (`BL03I-EA-ZEBRA-01:`) fans out the triggers and gates and drives the fast sample shutter.
- **A PandABox** (`BL03I-EA-PANDA-01:`) provides timing and HDF capture and drives the fast grid scan.

Both are modelled as `TimingController` devices, the same Family the 2-BM Timing device and I22's PandABoxes use, confirming that "timing-generation is a first-class device" generalizes across APS and Diamond. The fast grid scan that the PandA drives is modelled as a Method, not a device, even though dodal exposes it as one (`ZebraFastGridScan`, `PandAFastGridScan`); the scan is a recipe over the goniometer + detector, not an Asset (TRIG-1).

## The floor: GDA, hyperion / mx-bluesky, and Zocalo

A seam observation, recorded for the eventual Conductor work: I03's acquisition floor is Diamond's GDA plus the bluesky-based hyperion / mx-bluesky plan suite that drives MX data collection, with Zocalo handling the downstream processing, listed in the descriptor's `software_iocs_not_modeled` (along with the GDA baton, a beamline-control coordination token). These are control-system software, not CORA Assets. They are recorded because they are what a future CORA Conductor would orchestrate over or replace: I03 is a harder test of that seam than the imaging beamlines, because the MX floor already runs an autonomous bluesky plan suite, not a single scan engine.

See [Open questions](../questions.md) for the control and timing items still to confirm.
