# Detector

*The per-shot Jungfrau area detectors and the DAQ data plane they feed. Design-phase. The family folds and the acquisition ontology does not, the same finding as Alvra and Bernina.*

## The detectors fold; their acquisition does not

Cristallina's science detectors are PSI Jungfraus. The `slic` live config binds a 1.5M Jungfrau (`JF16T03V02`) plus a 0.5M I0 monitor (`JF20T01V01`) for the Cristallina-Q endstation, and an 8M (`JF17T16V01`) for Cristallina-MX. As devices, the Jungfraus reuse the `Camera` Family and present the Detector Role, exactly as they do at Alvra and Bernina and as the Eiger does at I03 and FXI. As devices, they fold cleanly.

What does **not** fold is how they are read. At a storage-ring beamline CORA arms a detector and polls its acquire PV until it reports Done, one frame per trajectory point. At an XFEL the detector is one source in a free-running stream: the SwissFEL `sf-daq` records every shot as a `bsread` message tagged by pulse-ID at beam rate, and a run is a stream of events correlated downstream by pulse-ID, not a walk over points. CORA's acquisition bodies (`collect` / `discrete` / `continuous`) and its sub-Hz scalar observation logbook have no representation for this (DAQ-1). Cristallina is the third PSI deployment to reach this gap (after Alvra and Bernina) and, with LCLS-MFX, the fourth XFEL deployment overall, now from a third controls library (`slic`).

## Provenance notes specific to Cristallina

- **The Jungfrau human-readable labels come from a commented `sf_daq_broker` block** (the serials and DAQ-crate mapping are live, the descriptions are commented), so the detector labels are carried `confirm` even though the serials are firm. Cristallina shares DAQ crate 10 with Bernina, on port 1 (DET-1).
- **The detector-per-configuration wiring** (which Jungfrau is active for Q vs MX) is selected by the `slic` experiment configuration; the inventory carries all three, and the active selection is to confirm (DET-1).

## How CORA references the data plane

The posture is the one CORA already uses for reconstructions and that Alvra and Bernina record: the per-shot data plane lives in PSI's `sf-daq` and the SwissFEL data API, and CORA references a `Dataset`, exactly as it references a reconstruction artifact through `ComputePort`. The Run aggregate stays the provenance envelope (it binds a Plan, a Subject, and a Method, and records what ran); the per-shot frames are not CORA rows. The missing actuation side, a primitive to begin and end an event-tagged DAQ run with pulse-ID as the correlation key, is sketched in the [event-stream-axis design note](../model.md), gated on a real trigger, and now wanted by four XFEL deployments.

## Detector geometry

The detectors carry the experiment geometry (sample-to-detector distance, the detector-arm position) that diffraction indexing needs; for the Q diffractometers the detector position is itself a diffractometer axis (the 2-theta arm). The calibrated geometry values are not in the `slic` manifest and are carried `confirm` (DET-1, DIFF-1).

See [Controls](controls.md) for the DAQ and timing systems, and [Open questions](../questions.md) for the detector items still to confirm.
