---
hide:
  - toc
---

# Replay scrubber

A live companion to the paper [Scrubbing the Run](papers.md). Drag the cursor to
fold one recorded overnight run to any instant: the readout reconstructs what the
run knew at that moment, who or what was driving it, and a content-addressed
badge recomputes a hash over the reconstructed recipe to prove the replay is
faithful.

The run is a lights-out, agent-supervised acquisition on the APS 2-BM micro-CT
beamline. The system conducts a rotation-axis centering alignment that converges,
the science scan begins, and the third projection is in flight when the beam
drops. A supervisor agent holds the run and auto-resumes it when the beam
returns, then the scan finishes and the dataset is written to disk.

<div id="cora-scrubber" aria-label="Interactive replay scrubber">Loading the interactive demo...</div>

Park the cursor at the beam-loss instant to see the third projection as an open
interval, its intent recorded before its outcome. Press **Play run** to watch the
whole arc unattended. Press **Tamper with record** to perturb the recorded recipe
and watch the fidelity badge honestly flip to *altered*.

The run data mirrors the paper's figure data file
([`data/lights_out_run.json`](https://github.com/xmap/cora/tree/main/papers/2026-vaxautosci-scrubber/data)),
which in turn mirrors the passing integration scenario
`test_2bm_lights_out_supervised_alignment.py`. Time spacing on the axis is
synthetic and compressed for readability; the overnight hold can last tens of
minutes.
