# Controls

*The control stack and trigger scheme. Design-phase, with the dodal-derived handles recorded.*

I22 runs the Diamond EPICS control stack. The crucial difference from the other design-phase scaffolds is that the control handles are **known**: Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) library records the real EPICS PV prefix for each device, so this scaffold carries `pv` on every device rather than leaving it empty.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. For I22 the EPICS PV prefixes are recorded from dodal (`src/dodal/beamlines/i22.py` and its device classes), carried `confirm` because a controls-library snapshot is not a guarantee against the live system. The PV naming follows the Diamond convention `BL<sector><branch>-<DOMAIN>-<TYPE>-<NN>:` (for example `BL22I-MO-DCM-01:` is beamline 22I, motion domain, double-crystal monochromator 01); the undulator and machine devices use the `SR22I` storage-ring root. The full handle list is in the [Inventory](../inventory.md).

What dodal does **not** give, and so is not invented: which access-gated hutch each device sits in (the PV encodes a functional zone, not a hutch or its PSS meaning, ENC-1), and the calibrated values behind the handles (limits, energy range, beam-center, camera lengths).

## Timing and triggering

Timing is handled by PandABox FPGA hardware, the same family Diamond uses across its bluesky beamlines:

- **Two PandABox units** (`BL22I-EA-PANDA-01:`, `BL22I-EA-PANDA-02:`) generate the triggers and gates and capture to HDF. dodal carries two more (Panda3 / Panda4) that are skip-flagged, so they are not modelled.

The scheme is modelled as `TimingController` devices, the same Family the 2-BM Timing device (the softGlueZynq box) uses, confirming that "timing-generation is a first-class device" generalizes from the APS pilot to a Diamond beamline. How the PandABoxes bind to the detectors and flux monitors (trigger fan-out, the master clock) is a Method concern carried as TRIG-1.

## The floor: GDA and bluesky

A seam observation, recorded for the eventual Conductor work: I22's acquisition floor is Diamond's GDA (Generic Data Acquisition) plus the bluesky/blueapi layer that dodal feeds, listed in the descriptor's `software_iocs_not_modeled`. These are control-system software, not CORA Assets. They are recorded because they are what a future CORA Conductor would orchestrate over or replace, the Diamond analogue of the APS tomoScan seam: I22 tests whether "replace the technique orchestrator" reads the same against a GDA/bluesky floor as against the APS EPICS-scan floor.

See [Open questions](../questions.md) for the control items still to confirm.
