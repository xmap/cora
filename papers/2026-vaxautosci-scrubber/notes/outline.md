# Outline, figures, and status

## Section-by-section (VGTC two-column; 6 pages total, ~4.5 body excl refs)

1. **Intro + contributions.** The overnight unattended-run audit motivation; the
   event-sourced-fold insight; scope honesty (conducted + agent-supervised, not
   agent-closed; deterministic supervisor); the four contributions. No figure.
2. **The auditor's tasks, Table 1.** T1-T4 mapped to event-log query and visual
   encoding.
3. **The replay scrubber, Figure 1 (centerpiece) + Figure 2 (fidelity).** The
   run-lifecycle / who-drove-it lane, convergence brackets, swim-lanes, the held
   band, and the fold-to-version cursor at the beam-loss instant; the fidelity
   badge.
4. **Interruption recovery, Figure 3.** The same run folded to two cursor
   positions: the interrupted projection open at beam loss (run held), closed after
   resume (run completed). T1.
5. **Substrate, Figure 5.** The one architecture figure; "substrate, not
   contribution."
6. **Related work.** Six neighborhoods; see related-work-map.md.
7. **Limitations and future work.**

## Figures

All data figures come from one passing scenario,
`test_2bm_lights_out_supervised_alignment.py`, exported to
`data/lights_out_run.json` by `data/build_lights_out_data.py`.

- F1 (data): scrubber overview, `figures/render_f1.py`.
- F2 (data): fidelity badge, `figures/render_f2.py`.
- F3 (data): interruption recovery (two-instant fold), `figures/render_f3.py`.
- Table 1 (data/design): task abstraction, in `sections/tasks.tex`.
- F5 (architecture): substrate schematic, `figures/render_f5.py`.

## Grounding

The scenario is a real, passing integration test: an operator starts an
unattended calibration run; CORA conducts a rotation-axis centering alignment
(4-iteration peak-bracket on `SampleTop_X`, converges); the science scan begins
and its third projection is in flight when the beam drops; the RunSupervisor agent holds the run and
auto-resumes it (RunResumed carries a Resume Decision); the run completes.
Default deps + a subjectless calibration run keep the safety envelope satisfied
without the full ESAF ceremony. Figure values mirror the scenario; timestamps
are staggered/compressed synthetically for a readable axis.

## Status

Full draft, builds on the official VGTC conference class (vendored). All
sections written; all figures rendered from the one run; references confirmed.
Open items: replace the placeholder author block (or set `[review]` +
`\onlineid` for double-blind); optionally add a downloadable PDF + a Build-papers
CI step and update the `docs/papers.md` card.
