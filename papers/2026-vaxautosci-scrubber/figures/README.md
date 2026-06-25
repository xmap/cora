# Figures

Five exhibits, only one of which is an architecture (box) figure: two data plots
(F1, F3), a task table (Table 1), a mechanism schematic with a real digest (F2),
and the architecture figure (F5). Keeping architecture to a single figure is the
deliberate venue-fit choice (see `../README.md`). The task abstraction is
realized as **Table 1** in the text (it replaces the originally-planned
"Figure 4").

| ID | Kind | Shows | Data source |
|---|---|---|---|
| F1 | data | The scrubber timeline: activity swim-lanes, nested convergence brackets colored by verdict, in-flight open intervals, draggable fold-to-version cursor. Centerpiece. | `../data/focus_run.json` (ready) |
| F2 | schematic | Fidelity check at the cursor: recorded hash vs recomputed hash, compare, verified. | `../data/focus_run.json` + `render_f2.py` (done) |
| F3 | data | Crash recovery: a dangling in-flight activity with no outcome, surfaced at the exact step index. | `../data/crash_run.json` (ready; rendered by `render_f3.py`) |
| Table 1 | data/design | Task abstraction: the four auditor tasks mapped to event-log query and visual encoding. | authored (in `sections/tasks.tex`) |
| F5 | architecture | The event-record / provenance substrate. The single architecture figure; "substrate, not contribution." | `render_f5.py` (done) |

Notes:
- F1 renders the clean completed run, so it shows no open intervals; the
  open-interval encoding is exercised by F3 (the crash case).
- Place source figures here (PDF or SVG preferred). Exported and compiled
  artifacts are gitignored.
