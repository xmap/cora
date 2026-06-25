# Figures

Five planned figures, four visualizing real exported data and one architecture
figure. The four-to-one ratio is deliberate (see `../README.md`). Source data
comes from the exported `test_2bm_alignment_focus.py` run; see
`../notes/outline.md`.

| ID | Kind | Shows |
|---|---|---|
| F1 | data | The scrubber timeline: activity swim-lanes, nested convergence brackets colored by verdict, in-flight open intervals, draggable fold-to-version cursor. Centerpiece. |
| F2 | data | Fidelity badge at the scrub point (inset on F1): content-addressed check that the replayed state matches the record. |
| F3 | data | Crash recovery: a dangling in-flight activity with no outcome, surfaced at the exact step index. |
| F4 | design/data | Task abstraction: the four auditor tasks mapped to event-log query and visual encoding. |
| F5 | architecture | The event-record / provenance substrate. The single architecture figure; labeled "substrate, not contribution." |

Place source figures here (PDF or SVG preferred). Exported and compiled
artifacts are gitignored.
