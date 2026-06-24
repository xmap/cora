# Controls

*The control stack and trigger scheme. Design-phase, with the dodal-derived handles recorded.*

I15-1 runs the Diamond EPICS control stack. As at I22 and I03, the control handles are **known**: Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) library records the real EPICS PV prefix for each device, so this scaffold carries `pv` on every device.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. For I15-1 the EPICS PV prefixes are recorded from dodal (`src/dodal/beamlines/i15_1.py` and its device classes), carried `confirm`. The PV naming follows the Diamond convention `BL<sector><branch>-<DOMAIN>-<TYPE>-<NN>:` (for example `BL15I-OP-LAUE-01:` is beamline 15I, optics domain, bent-Laue mono 01). The full handle list is in the [Inventory](../inventory.md).

dodal also records two real **interlock** readbacks (`BL15I-PS-IOC-02:M11:LOP`, `BL15I-VA-OMRON-01:INT3:ILK`). These are **not** device handles: an interlock is the read-only permit behind the Enclosure aggregate, so they are carried as the Enclosure `permit_signal` candidates, not as equipment Assets (INTERLOCK-1, PSS-1).

## Timing and triggering

Timing is handled by a Zebra FPGA box (`BL15I-EA-ZEBRA-01:`), modelled as a `TimingController` device, the same Family the 2-BM Timing device and the I22 / I03 boxes use. It generates the triggers and gates and drives the fast shutter (whose set/get PVs are Zebra soft-IO lines).

## The floor: GDA and bluesky

A seam observation, recorded for the eventual Conductor work: I15-1's acquisition floor is Diamond's GDA plus the bluesky layer that dodal feeds, listed in the descriptor's `software_iocs_not_modeled` (along with `puck_detect`, an image-processing web service for puck/lid detection that is software, not a device). These are control-system software, not CORA Assets; they are what a future CORA Conductor would orchestrate over or replace.

See [Open questions](../questions.md) for the control items still to confirm.
