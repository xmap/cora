# Figures

Four data exhibits and one architecture figure, all drawn from the single
lights-out, agent-supervised run in `../data/lights_out_run.json` (except the
authored substrate diagram). The task abstraction is realized as **Table 1** in
the text. The four-data-to-one-architecture ratio is deliberate (see
`../README.md`).

| ID | Kind | Shows | Source |
|---|---|---|---|
| F1 | data | The scrubber: a run-lifecycle / who-drove-it lane (operator vs supervisor), the held band, verdict-tinted iteration bands, activity swim-lanes, the in-flight third projection, the science scan continuing after resume, and the fold-to-version cursor at the beam-loss instant. Centerpiece. | `render_f1.py` over `lights_out_run.json` |
| F2 | data | The fidelity badge: recorded content-addressed hash vs the hash recomputed from the folded state -> verified. | `render_f2.py` over `lights_out_run.json` |
| F3 | data | Interruption recovery: the same run folded to two cursor positions, the interrupted projection (projection 3) open at beam loss (run held) and closed after resume (run completed). | `render_f3.py` over `lights_out_run.json` |
| Table 1 | data/design | Task abstraction: the four auditor tasks mapped to event-log query and visual encoding. | authored (`sections/tasks.tex`) |
| F5 | architecture | The event-record / provenance substrate. The single architecture figure; "substrate, not contribution." | `render_f5.py` (authored schematic) |

Notes:
- All three data figures come from one passing scenario, so the figures are
  consistent with each other and with the run the paper describes.
- Regenerate: run the three `render_f*.py` (after `data/build_lights_out_data.py`).
  Exported and compiled artifacts are gitignored; the rendered figure PDFs and
  PNGs are tracked as assets.
