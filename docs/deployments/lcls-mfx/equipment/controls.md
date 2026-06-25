# Controls

*The control stack, the beam-synchronous timing, and the event-driven DAQ. Design-phase, with the `pcdshub`-derived handles recorded.*

MFX runs the `pcdshub` EPICS stack for slow control, plus a separate event-driven DAQ for the per-shot data. As at the Diamond exercises, the control handles are **known**: `pcdshub`'s `device_config/db.json` and the worked `mfx/beamline.py` record the real EPICS PV prefix for each device, so this scaffold carries `pv` on every device.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. For MFX the EPICS PV prefixes are recorded from `pcdshub`, carried `confirm` because a controls snapshot is not a guarantee against the live system. The PV naming is the LCLS convention `HUTCH:STAND:DEVICE:INSTANCE` with colon-delimited components (for example `MFX:DG1:IPM` is the MFX hutch, diagnostic stand 1, intensity-position monitor); the front-end and transport use `FEE1` / `XRT` / `HFX` roots. The full handle list is in the [Inventory](../inventory.md). What `pcdshub` does not give, and so is not invented: which access-gated hutch each device sits in (the prefix encodes a beamline-line zone, not a hutch, ENC-1), and the calibrated values behind the handles.

## Timing and triggering

Timing is handled by the **EventSequencer** (`ECS:SYS0:7`, with a spare on `ECS:SYS0:12`), modelled as a `TimingController`, the same Family the 2-BM Timing device and the Diamond / APS PandABoxes use. It plays a beam-synchronous sequence of lines, each `[beam_code, delta_beam, delta_fiducial, burst_count]`, that gate acquisition at beam rate.

The Family fits the device; what does not fit is the sequence content. "Acquire on event-code N at beam rate R, burst B" is a typed acquisition concept with no home in CORA's timing model, which today knows only `Internal` / `ExternalEdge` / `ExternalLevel` trigger modes. The event-code sequence would be carried as opaque setpoints until a typed parameter shape is earned (TIMING-1). This is the timing half of the per-shot acquisition gap.

## The floor: the DAQ, psana, and the bluesky suite

A seam observation, recorded for the eventual Conductor work. MFX's acquisition floor is the LCLS DAQ (`psdaq` / `pcdsdaq`; the per-shot, pulse-ID-tagged event acquisition), `psana` (the per-shot analysis plane), the `hutch-python` / `nabs` bluesky-based scan and DAQ-run suite, and AMI (online per-shot monitoring), all listed in the descriptor's `software_iocs_not_modeled`. Also on the floor is the BTPS, the Beam Transport Protection System that interlocks the pump-probe laser (LASER-1).

These are control-system software, not CORA Assets. They are recorded because they are what a future CORA Conductor would orchestrate over or reference. MFX is the hardest test of that seam in the whole deployment set: unlike a storage-ring scan engine, the LCLS DAQ is an event-driven, pulse-ID-correlated data plane that CORA does not poll but references. The shape that reference takes (a `Dataset` handle, with the Run as the provenance envelope) is sketched in the [event-stream-axis design note](../model.md); the per-shot DAQ run is the deepest gap this exercise found (DAQ-1).

See [Open questions](../questions.md) for the control and timing items still to confirm.
