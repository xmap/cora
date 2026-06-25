# Figures

Four data exhibits and one architecture figure. The four-to-one ratio is
deliberate (see `../README.md`). The task abstraction is realized as **Table 1**
in the text (it replaces the originally-planned "Figure 4").

| ID | Kind | Shows | Data source |
|---|---|---|---|
| F1 | data | The scrubber timeline: activity swim-lanes, nested convergence brackets colored by verdict, in-flight open intervals, draggable fold-to-version cursor. Centerpiece. | `../data/focus_run.json` (ready) |
| F2 | data | Fidelity badge at the scrub point (inset on F1). | `../data/focus_run.json` (ready) |
| F3 | data | Crash recovery: a dangling in-flight activity with no outcome, surfaced at the exact step index. | conductor-path run (pending; see `../data/README.md`) |
| Table 1 | data/design | Task abstraction: the four auditor tasks mapped to event-log query and visual encoding. | authored (in `sections/tasks.tex`) |
| F5 | architecture | The event-record / provenance substrate. The single architecture figure; "substrate, not contribution." | authored |

Notes:
- F1 renders the clean completed run, so it shows no open intervals; the
  open-interval encoding is exercised by F3 (the crash case).
- Place source figures here (PDF or SVG preferred). Exported and compiled
  artifacts are gitignored.
