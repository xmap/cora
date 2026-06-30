# Detector

*The per-shot Jungfrau area detector and the DAQ data plane it feeds. Design-phase. This is where the family folds and the acquisition ontology does not, the same finding as LCLS-MFX.*

## The detector folds; its acquisition does not

Alvra's science detector is a PSI Jungfrau: `eco` binds Alvra to one named `JF_4.5M` (the von Hamos 4.5M, serial `JF02T09V03` inferred via `sf_daq_broker`), and the broker lists further Alvra Jungfrau options (a 16M, a 4M, a 2M TXS, and 0.5M flex variants), so which is in use is to confirm (DET-1). As a device, the Jungfrau reuses the `Camera` Family and presents the Detector Role, exactly as the Eiger does at I03 and FXI and the area detector does at LCLS-MFX. As a device, it folds cleanly.

What does **not** fold is how it is read. At a storage-ring beamline CORA arms a detector and polls its acquire PV until it reports Done, one frame per trajectory point. At an XFEL the detector is one source in a free-running stream: the SwissFEL `sf-daq` records every shot as a `bsread` message tagged by pulse-ID at beam rate, and a "run" is a stream of events correlated downstream by pulse-ID, not a walk over points. CORA's acquisition bodies (`collect` / `discrete` / `continuous`) and its sub-Hz scalar observation logbook have no representation for this (DAQ-1). This is the same gap LCLS-MFX exposed; Alvra is the second XFEL to confirm it, against an independently-built DAQ.

## How CORA references the data plane

The posture this exercise lands on (sketched, not built) is the one CORA already uses for reconstructions: the per-shot data plane lives in PSI's `sf-daq` and the SwissFEL data API, and CORA references a `Dataset`, exactly as it references a reconstruction artifact through `ComputePort`. The Run aggregate stays as the provenance envelope (it binds a Plan, a Subject, and a Method, and records what ran); the per-shot frames are not CORA rows. What is missing, and what the [event-stream-axis design note](../model.md) sketches, is the actuation side: a primitive to begin and end an event-tagged DAQ run with pulse-ID as the correlation key. That is a new event-stream axis, gated on a real trigger, and now wanted by two XFEL deployments.

## Detector geometry

The detector carries the experiment geometry (sample-to-detector distance, beam center) that serial-crystallography indexing and emission-spectrometer dispersion need. These calibrated values are not in the `eco` manifest (which carries no units or geometry) and are carried `confirm` (DET-1).

See [Controls](controls.md) for the DAQ and timing systems, and [Open questions](../questions.md) for the detector items still to confirm.
