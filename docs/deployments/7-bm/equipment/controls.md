# Controls

*The control stack and trigger scheme. Design-phase; handles not yet recorded.*

7-BM runs on the APS EPICS control stack, the same stack 2-BM uses. Unlike TomoWISE (which runs MAX IV Tango/Sardana), there is no control-system difference from the APS pilot here.

## Device handles

CORA models each device's control handle as an opaque string set at the edge. For 7-BM the EPICS PV names are not yet recorded in this scaffold, so every device's handle is left empty in the [descriptor](../inventory.md) rather than filled with an invented value. Wiring each Asset to a real PV is tracked by CTRL-1 on [Open questions](../questions.md).

## Timing and triggering

Timing is a heavier subsystem at 7-BM than at 2-BM, because the time-resolved techniques (high-speed imaging, radiography) need hardware-gated triggering synchronized to the storage ring. The scheme:

- **Two Stanford DG645 delay generators.** One is synced to the storage-ring P0 signal (271 kHz); the other delays the chopper-to-camera trigger so the camera fires when a chopper opening reaches the beam.
- **A softGlue FPGA** for low-level logic (counters, gates, signal decimation).
- **The Machine Status Link P0 reference**, synchronized to the electron beam.
- **A top-up inhibit signal** that goes high before a ring top-up and vetoes acquisition during the unstable window, so time-resolved data is not taken during top-up.

The whole scheme is modelled as a single `TimingController` device carrying it, mirroring the 2-BM Timing device (the softGlueZynq box). Whether any of these elements deserves separate modelling is TIMING-1.

## The floor: several orchestrators, not one

A 7-BM-specific seam observation, recorded for the eventual Conductor work: where 2-BM has one acquisition orchestrator (tomoScan), 7-BM's floor carries several technique-specific ones, listed in the descriptor's `software_iocs_not_modeled`:

- **tomoScan** for tomography (shared with 2-BM).
- **DataGrabber** (Java) for time-resolved radiography, handshaking over the EPICS busy record `7bmb1:rad:get_data`.
- **The ADQ14 Python scripts** bridging the EPICS scan record to the digitizer soft IOC.
- **The EPICS scan record** for step scans.
- **The high-speed-imaging string sequence** for chopper-gated movie bursts.

These are control-system software, not CORA Assets. They are recorded here because they are what a future CORA Conductor would orchestrate over or replace: 7-BM tests whether "replace the technique orchestrator" generalizes across several distinct floor engines, where 2-BM had only one.

See [Open questions](../questions.md) for the control and timing items still to confirm.
