# Controls

*The control stack, the beam-synchronous timing, and the event-driven DAQ. Design-phase, with the `eco`-derived handles recorded.*

Alvra runs the PSI EPICS stack for slow control, plus the SwissFEL event-driven DAQ for the per-shot data. As at the LCLS-MFX and Diamond exercises, the control handles are **known**: PSI's [`eco`](https://github.com/paulscherrerinstitute/eco) library records the real EPICS PV prefix for each device in `eco/alvra/config.py`, so this scaffold carries `pv` on every device.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. For Alvra the EPICS PV prefixes are recorded from `eco`, carried `confirm` because a controls snapshot is not a guarantee against the live system, and because `eco` is code, not a flat manifest: each device's driver class derives its motor axes from the prefix by string concatenation, so the axis-level PVs are derived rather than read from a table. The PV naming is the SwissFEL convention with hyphen-delimited components keyed by section, `SARFE10-` for the Aramis front end, `SAROP11-` for the Aramis optics, and `SARES11-` / `SLAAR11-` for the Alvra endstation and laser (for example `SARES11-XSAM125` is the Alvra endstation sample manipulator). The full handle list is in the [Inventory](../inventory.md).

What `eco` does not give, and so is not invented: the motor units and limits (these live on the EPICS records at runtime, not in the manifest), which access-gated hutch each device sits in (the prefix encodes a beamline-line section, not a hutch, ENC-1), and the Aramis source parameters. One `eco`-specific ambiguity is recorded rather than resolved: several Alvra drivers reference `SAROP21-*` PVs (a sibling Aramis line) for an aperture and an energy readback, which may be a real cross-line dependency or a copy-paste artifact in the library (XREF-1).

## Timing and triggering

Timing is handled by the **SwissFEL event system**: EVR (event-receiver) units, such as the one driving the laser shutter (`SLAAR11-LTIM01-EVR0`), distribute a beam-synchronous trigger pattern that gates acquisition at beam rate. CORA models the event timing as a `TimingController`, the same Family the 2-BM Timing device, the Diamond / APS PandABoxes, and the LCLS EventSequencer use.

The Family fits the device; what does not fit is the trigger-pattern content. "Acquire on event-code N at beam rate R" is a typed acquisition concept with no home in CORA's timing model, which today knows only `Internal` / `ExternalEdge` / `ExternalLevel` trigger modes. The trigger pattern would be carried as opaque setpoints until a typed parameter shape is earned (TIMING-1). This is the timing half of the per-shot acquisition gap, and Alvra reaches it the same way LCLS-MFX did.

## The floor: sf-daq, bsread, and the eco scan suite

A seam observation, recorded for the eventual Conductor work. Alvra's acquisition floor is `sf-daq` (the per-shot, pulse-ID-tagged event acquisition broker), `bsread` / `mflow` (the beam-synchronous ZMQ data streaming transport), the `eco` / `slic` Python scan and acquisition suite (the layer this descriptor is mined from), and the SwissFEL data API / databuffer (the per-shot data-analysis plane), all listed in the descriptor's `software_iocs_not_modeled`.

These are control-system software, not CORA Assets. They are recorded because they are what a future CORA Conductor would orchestrate over or reference. Alvra is, with LCLS-MFX, the hardest test of that seam in the deployment set: unlike a storage-ring scan engine, `sf-daq` is an event-driven, pulse-ID-correlated data plane that CORA does not poll but references. The shape that reference takes (a `Dataset` handle, with the Run as the provenance envelope) is sketched in the [event-stream-axis design note](../model.md); the per-shot DAQ run is the deepest gap this exercise re-confirms (DAQ-1).

Note the provenance contrast with LCLS-MFX: the Alvra descriptor is mined from `eco`, a Python *device-control library*, where the same beamline at SLAC was mined from `pcdshub`'s `happi` *device database*. That the same architectural gaps surface from two differently-shaped control stacks is the reinforcement this second XFEL exists to provide.

See [Open questions](../questions.md) for the control and timing items still to confirm.
