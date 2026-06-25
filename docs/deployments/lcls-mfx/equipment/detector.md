# Detector

*The per-shot area detector and the DAQ data plane it feeds. Design-phase. This is where the family folds and the acquisition ontology does not.*

## The detector folds; its acquisition does not

MFX's science detector (a Rayonix MX340-XFEL, ePix10k, or Jungfrau, depending on the experiment, DET-1) reuses the `Camera` Family and presents the Detector Role, exactly as the Eiger does at I03 and FXI. As a device, it folds cleanly.

What does **not** fold is how it is read. At a storage-ring beamline CORA arms a detector and polls its `Acquire_RBV` PV until it reports Done, one frame per trajectory point. At an XFEL the detector is one source in a free-running stream: the LCLS DAQ records every shot, tagged by pulse-ID and fiducial at beam rate (120 Hz at LCLS, up to roughly 1 MHz on LCLS-II), and a "run" is millions of events correlated downstream by pulse-ID, not a walk over points. CORA's acquisition bodies (`collect` / `discrete` / `continuous`) and its sub-Hz scalar observation logbook have no representation for this (DAQ-1).

## How CORA references the data plane

The posture this exercise lands on (sketched, not built) is the one CORA already uses for reconstructions: the per-shot data plane lives in SLAC's `psana` / DAQ, and CORA references a `Dataset`, exactly as it references a reconstruction artifact through `ComputePort`. The Run aggregate stays as the provenance envelope (it binds a Plan, a Subject, and a Method, and records what ran); the per-shot frames are not CORA rows. What is missing, and what the [event-stream-axis design note](../model.md) sketches, is the actuation side: a primitive to begin and end an event-tagged DAQ run (events or duration, record on or off), with pulse-ID as the correlation key. That is a new event-stream axis, gated on a real trigger.

## The detector translation and geometry

The detector sits on a translation stage (a `LinearStage`) that sets the sample-to-detector distance, and carries the experiment geometry (distance, beam center) that serial-crystallography indexing needs. These calibrated values are not in `pcdshub`'s device database and are carried `confirm` (DET-1).

See [Controls](controls.md) for the DAQ and timing systems, and [Open questions](../questions.md) for the detector items still to confirm.
