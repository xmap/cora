# Scrubbing the Run (VAxAutoSci 2026 pilot)

Replay-native provenance visualization for closed-loop beamline experiments.
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
- **Status:** Drafting. Abstract, contributions, and Related Work are written;
  task abstraction, scrubber, crash-recovery, substrate, and limitations are
  stubs. No figures yet. No compiled PDF yet.

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
2. The Auditor's Tasks: Figure 4 (task abstraction, the VIS spine).
3. The Replay Scrubber: Figure 1 (centerpiece, real data) + Figure 2 inset
   (fidelity badge).
4. Crash Recovery: Figure 3 (in-flight gap).
5. Substrate: Figure 5 (the one capped architecture figure).
6. Related Work (drafted).
7. Limitations and Future Work.

## Figure inventory

Five figures, four of which visualize real exported data, one architecture
figure. See `figures/README.md`. That four-to-one ratio is the structural
defense against the "this is a backend paper, not a VA paper" reject.

## Framing risk and how this paper neutralizes it

The risk: at an IEEE VIS workshop, a paper about event sourcing and an
append-only store reads as "great infrastructure, wrong venue." Neutralizers:
lead with the human task (Figure 4 before any architecture); keep four of five
figures as data visualizations and cap architecture at one; say "conducted"
(closed-loop, semi-autonomous), not "self-driving," and do not claim an
agent-closed perceive-decide-act loop; render immutability as a one-sentence
visual fidelity claim, not a systems section; get every repo-checkable fact
exactly right.

## Data grounding

The centerpiece data comes from the passing integration scenario
`apps/api/tests/integration/scenarios/test_2bm_alignment_focus.py` (a
four-iteration peak-bracket autofocus search on APS 2-BM: setpoint and check
activities, `in_flight` markers, per-iteration `converged` verdicts). The
interrupted-run figure removes one activity outcome to leave a dangling
`in_flight` marker.

## Build

This folder does not vendor the venue's LaTeX class. To compile:

1. Download the VIS 2026 author kit and place `vgtc.cls`, `abbrv-doi.bst`, and
   supporting `.sty` files in this folder.
2. Reconcile the front-matter macros in `main.tex` with that kit.
3. `latexmk -pdf main.tex` (or `pdflatex main && bibtex main && pdflatex main`
   twice).

Build artifacts are gitignored.

## Camera-ready checklist (deferred)

- [ ] Produce the five figures (export real run data; see `notes/outline.md`).
- [ ] Fill the stub sections.
- [ ] Confirm the four `% TODO confirm` references in `refs.bib`.
- [ ] Add `papers/<slug>/<slug>.pdf` and a `Build papers` step in
      `.github/workflows/docs.yml` (see `../README.md`).
- [ ] Update the card in `docs/papers.md` with a PDF download link.

## Notes

- `notes/related-work-map.md`: the consolidated related-work landscape.
- `notes/research-findings.md`: verified findings, verdicts, citation hygiene,
  refuted claims, and method caveats from the literature passes.
- `notes/outline.md`: section outline, figures, and the build/write plan.
