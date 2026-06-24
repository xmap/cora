# Controls

*The control stack. Design-phase, with the dodal-derived handles recorded.*

I11 runs the Diamond EPICS control stack. As at the other Diamond beamlines, the control handles are **known**: Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) library records the real EPICS PV prefix for each device, so this scaffold carries `pv` on every device.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. For I11 the EPICS PV prefixes are recorded from dodal (`src/dodal/beamlines/i11.py` and its device classes), carried `confirm`. The PV naming follows the Diamond convention `BL<sector><branch>-<DOMAIN>-<TYPE>-<NN>:` (for example `BL11I-MO-DIFF-01:` is beamline 11I, motion domain, diffractometer 01). The full handle list is in the [Inventory](../inventory.md).

What dodal does **not** give, and so is not invented: which access-gated hutch each device sits in (ENC-1), and the calibrated values behind the handles.

## Timing and triggering

The dodal i11 module exposes **no FPGA timing box** (no Zebra or PandABox factory), unlike I03 and I15-1. So triggering is not modelled in this scaffold; whether powder-diffraction acquisition uses a hardware trigger chain or step scans is a deployment question that would surface with the powder-diffraction Method (TECH-1).

## The floor: GDA and bluesky

A seam observation, recorded for the eventual Conductor work: I11's acquisition floor is Diamond's GDA plus the bluesky layer that dodal feeds, listed in the descriptor's `software_iocs_not_modeled`. These are control-system software, not CORA Assets; they are what a future CORA Conductor would orchestrate over or replace.

See [Open questions](../questions.md) for the control items still to confirm.
