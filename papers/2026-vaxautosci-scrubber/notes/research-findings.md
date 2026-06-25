# Research findings (literature passes)

Four deep-research passes (fan-out search, source fetch, adversarial 3-vote
verification, synthesis), roughly 95 sources across provenance visualization,
self-driving-lab VA, replay/time-travel debugging, tamper-evident provenance,
conformance checking, reproducibility badges, and autonomous-experiment
dashboards. This file keeps the lit review auditable.

## Closest baselines (use as the named contrasts)

- **Verdant** (Kery & Myers): the only prior system pairing recorded history
  with a draggable timeline scrubber. Beaten because its replay re-executes and
  ignores original dependencies (no fidelity), and targets a local notebook.
- **Atlas** (arXiv 2502.19567): closest fidelity-mechanism (content-addressed
  hash-vs-reference check on ML artifacts), but programmatic, discrete
  artifacts, no UI.
- **PM4Py alignment table**: closest verdict-coloring (per-move type color), but
  positional axis, no iteration brackets, no interrupted-step marker.
- **Pernosco/rr**: closest record-then-fold posture; the guarantee is internal,
  never rendered.

## Citation hygiene (fix before camera-ready)

- CHI 2019 foraging / 15-participant / median-80% study is DOI
  10.1145/3290605.3300322, NOT the VL/HCC 2018 Verdant DOI.
- Cite the IPAW 2006 VisTrails version for the version-tree / delta text, not
  only the SIGMOD demo.
- Rozinat & van der Aalst: cite the 2008 Information Systems journal; pair with
  the modern four-dimension conformance framing (fitness, precision,
  generalization, simplicity); note token-replay was superseded by
  alignment-based conformance around 2011.
- Rehse survey: arXiv 2209.09712 = HICSS-56 (2023) = the earlier "Rehse 2022";
  one item, cite once. Häge & Rehse 2025 = "best available recent," not
  "canonical."
- Online conformance: van Zelst et al., Int. J. Data Science and Analytics
  (2019), doi 10.1007/s41060-017-0078-6 (the "Computing 2019" pointer was a
  venue near-miss).
- ChemOS 2.0 (Sim et al.) and the Atlas Bayesian-optimization library (Hickman
  et al.) are distinct works; do not conflate. Note there are two different
  "Atlas" systems in this space: the C2PA ML-provenance Atlas (cited) and an
  unrelated BO library; never name both "Atlas" in the prose.
- ACM badges: cite the acm.org policy page, not the reviewers.acm.org training
  URL. Whole Tale: cite readthedocs recorded-runs or Brinckman et al. (FGCS
  2019), not the landing page.
- Workflow-Run RO-Crate per-step entities are tool-execution CreateActions
  referenced by step-level ControlActions.
- Adriansyah's alignments thesis was not adjudicated on content; do not claim it
  "lacks" temporal viz. Safe statement: the canonical alignment idiom is
  post-hoc, complete-trace, move-type, with no iteration axis.

## Refuted claims (do not assert)

- No standard verdict color mapping (blue=conform / red=deviate) exists in
  process-mining tools (refuted 3-0).
- Do not cite the NSLS-II Bluesky paper (arXiv 2509.22959) as SOTA or as
  gap-confirmation (refuted twice).
- QIIME 2 Provenance Replay does NOT do MD5 tamper-detection (refuted).

## Word-choice guardrails

- Do not say Tsuchinoko or Bluesky have "no replay" (Tsuchinoko has a
  re-execution Replay button; databroker can re-emit documents). Say: no
  scrubbable time-cursor reconstruction with a fidelity check.
- Do not say BestEffortCallback does "no analysis" (it does live peak fitting).

## Method caveat

WebSearch was blocked during the verification stage across passes, so
contradiction checks relied on primary sources (paper PDFs, official docs, live
source code) rather than adversarial secondary search. Strong for absence-of-
feature and code-behavior claims; state it.

## Residual (optional) follow-ups

Both turned up nothing that changes the verdicts, but were thinner: alignment-
based or online-conformance dashboards with a temporal verdict axis; and
self-driving-lab dashboards beyond those adjudicated. Re-check only if a
reviewer pushes.
