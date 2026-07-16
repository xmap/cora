# Scrubbing the Run (VAxAutoSci 2026 pilot)

Replay-native provenance visualization for agent-supervised beamline experiments.
The fold an event-sourced system of record already uses to reconstruct state
becomes a draggable time cursor an auditor scrubs through a recorded run, with a
content-addressed fidelity badge that proves the replayed state matches the
record.

## At a glance

- **Venue:** VAxAutoSci, Visual Analytics in the Age of Autonomous Science (an
  IEEE VIS 2026 workshop), Boston, November 9 2026.
- **Format:** short paper, 4-6 pages excluding references, two-column VGTC
  conference style, published to IEEE Xplore.
- **Deadline:** July 8 2026 (23:59 AoE).
- **Status:** Full draft, builds on the official VGTC conference class.
  `main.tex` builds to 7 pages total; the body fits inside the 4-6 page limit,
  with references beginning on page 6 and continuing to page 7. All sections
  written; all figures (F1, F2, F3, Table 1, F5) rendered from real run data;
  references confirmed.

## Topic landing (PCS)

Primary: Provenance, reproducibility, and auditability. Secondary: Evaluation
of designing, monitoring, and steering autonomous processes. Tertiary:
Uncertainty, trust, and reliability.

## Thesis

Autonomous-science provenance is machine-speed, decision-dense, and multi-pass,
so post-hoc provenance graphs lose the temporal and causal texture an auditor
needs. An event-sourced record makes provenance directly scrubbable: the same
fold the backend uses to re-derive state becomes a time cursor, and a
content-addressed expansion hash lets the visualization verify, not just assert,
that the replayed state is faithful.

## Section map

1. Introduction and contributions (no figure).
2. The Auditor's Tasks: Table 1 (task abstraction, the VIS spine).
3. The Replay Scrubber: Figure 1 (centerpiece) + Figure 2 (fidelity badge).
4. Interruption Recovery: Figure 3 (fold to two cursor positions).
5. Substrate: Figure 5 (the one capped architecture figure).
6. Related Work.
7. Limitations and Future Work.

## Figure inventory

Four data exhibits (F1, F2, F3, Table 1) and one architecture figure (F5). See
`figures/README.md`. That four-to-one ratio is the structural defense against
the "this is a backend paper, not a VA paper" reject.

## Framing risk and how this paper neutralizes it

The risk: at an IEEE VIS workshop, a paper about event sourcing and an
append-only store reads as "great infrastructure, wrong venue." Neutralizers:
lead with the human task (Table 1 before any architecture); keep the data
exhibits dominant and cap architecture at one figure; say "conducted" and
"agent-supervised," not "self-driving," and do not claim an agent-closed
perceive-decide-act loop (the supervisor is a deterministic agent); render
immutability as a one-sentence visual fidelity claim, not a systems section; get
every repo-checkable fact exactly right.

## Data grounding

All figures come from one passing integration scenario,
`apps/api/tests/integration/scenarios/test_2bm_lights_out_supervised_alignment.py`:
an operator starts an unattended calibration run; CORA conducts a rotation-axis
centering alignment (four-iteration peak-bracket on `SampleTop_X`, converges); the
science scan begins and its third projection is in flight when the beam drops;
the RunSupervisor agent holds the run and auto-resumes it (RunResumed carries a
Resume Decision); the fly-scan is restarted and the run completes. Figure values
mirror the scenario (`data/lights_out_run.json`).

## Layout

The prose lives in `sections/*.tex` (abstract, intro, tasks, scrubber,
crash-recovery, substrate, related-work, limitations). Two drivers read the
same fragments so the text never drifts:

- `main.tex`: the submission, in the venue's official VGTC class.
- `preview.tex`: a two-column build under `IEEEtran` (conference). The venue
  publishes to IEEE Xplore, so this is a close proxy for the VGTC layout and
  page count, and it builds today without the VGTC class. Not the submission;
  exact spacing differs (VGTC 9pt is a touch denser than IEEEtran 10pt).

Edit a fragment once; both builds pick it up.

## Build

The official VGTC conference class is vendored here (`vgtc.cls` +
`abbrv-doi*.bst`, from `github.com/ieeevgtc/vgtc_conference_latex`; see
`VGTC_TEMPLATE_README.txt`), so the submission builds directly:

    latexmk -pdf main.tex

This produces the exact VGTC conference format: 7 pages total, with the body
inside the 4-6 page limit and references beginning on page 6. Submit the
LaTeX-built `main.pdf` from this folder; do not submit a macOS Preview-resaved
desktop copy. For double-blind review, switch to
`\documentclass[review]{vgtc}` and set `\onlineid` to the assigned id.

`preview.tex` is a no-frills IEEEtran proxy over the same shared sections, for
quick reading. Build artifacts (PDFs, `.aux`, `.bbl`, ...) are gitignored; the
vendored class and bibstyle files are tracked.

## Camera-ready checklist

- [x] Produce the figures (F1, F2, F3, Table 1, F5) from real run data.
- [x] Fill all sections.
- [x] Confirm the four flagged references in `refs.bib`.
- [x] Build `main.tex` on the official VGTC class (7 pages total, body within
      the 4-6 page limit).
- [x] Author block: Doga Gursoy (corresponding, dgursoy@anl.gov) and Francesco
      De Carlo (no email), Advanced Photon Source, Argonne National Laboratory,
      single-blind. For double-blind instead, set `\documentclass[review]{vgtc}`
      + the assigned `\onlineid`. Confirm the corresponding email.
- [ ] Optional: source F3's crash from a real conductor run (currently a
      labeled truncation).
- [ ] Add `papers/<slug>/<slug>.pdf` and a `Build papers` step in
      `.github/workflows/docs.yml` (see `../README.md`), then update the
      `docs/papers.md` card with a PDF download link.

## Notes

- `notes/related-work-map.md`: the consolidated related-work landscape.
- `notes/research-findings.md`: verified findings, verdicts, citation hygiene,
  refuted claims, and method caveats from the literature passes.
- `notes/outline.md`: section outline, figures, and the build/write plan.
