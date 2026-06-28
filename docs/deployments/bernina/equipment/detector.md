# Detector

*The per-shot Jungfrau area detector and the DAQ data plane it feeds. Design-phase. The family folds and the acquisition ontology does not, the same finding as Alvra and LCLS-MFX.*

## The detector folds; its acquisition does not

Bernina's science detector is a PSI Jungfrau. `eco` wires a 1.5M Jungfrau (`JF01T03V01`) inline, and `sf_daq_broker` lists Bernina's main 16M (`JF07T32V02`) plus I0, vacuum, fluorescence, and RIXS 0.5M variants. As a device, the Jungfrau reuses the `Camera` Family and presents the Detector Role, exactly as it does at Alvra and as the Eiger does at I03 and FXI. As a device, it folds cleanly.

What does **not** fold is how it is read. At a storage-ring beamline CORA arms a detector and polls its acquire PV until it reports Done, one frame per trajectory point. At an XFEL the detector is one source in a free-running stream: the SwissFEL `sf-daq` records every shot as a `bsread` message tagged by pulse-ID at beam rate, and a time-resolved diffraction "run" is a stream of events correlated downstream by pulse-ID and pump-probe delay, not a walk over points. CORA's acquisition bodies (`collect` / `discrete` / `continuous`) and its sub-Hz scalar observation logbook have no representation for this (DAQ-1). Bernina is the third XFEL deployment to reach this gap (after LCLS-MFX and Alvra), and the first to reach it through diffraction rather than spectroscopy or crystallography, which is the point: the gap is about the acquisition paradigm, not the technique.

## Two unknowns specific to Bernina

- **Which detector attaches to which diffractometer is external (CONFIG-1).** The `eco` driver reads the per-diffractometer detector membership from the non-public `bernina_config` JSON, so the inventory carries the Jungfrau variants but not their wiring to the GPS / XRD platforms.
- **The `eco` and `sf_daq_broker` version strings differ for the 16M** (`JF07T32V01` in `eco`, `JF07T32V02` in the broker). Both are carried `confirm` rather than picking one (DET-1).

## How CORA references the data plane

The posture is the one CORA already uses for reconstructions and that Alvra records: the per-shot data plane lives in PSI's `sf-daq` and the SwissFEL data API, and CORA references a `Dataset`, exactly as it references a reconstruction artifact through `ComputePort`. The Run aggregate stays the provenance envelope (it binds a Plan, a Subject, and a Method, and records what ran); the per-shot frames are not CORA rows. The missing actuation side, a primitive to begin and end an event-tagged DAQ run with pulse-ID as the correlation key, is sketched in the [event-stream-axis design note](../model.md), gated on a real trigger, and now wanted by three XFEL deployments.

## Detector geometry

The detector carries the experiment geometry (sample-to-detector distance, the detector-arm position) that diffraction indexing needs; for Bernina the detector position is itself a diffractometer axis (the `delta` arm and detector translation). The calibrated geometry values are not in the `eco` manifest and are carried `confirm` (DET-1, DIFF-1).

See [Controls](controls.md) for the DAQ and timing systems, and [Open questions](../questions.md) for the detector items still to confirm.
