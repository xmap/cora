# Outline, figures, and build plan

## Section-by-section (target 5 pages, 4-6 allowed)

1. **Intro + thesis (~1 col).** Open with the auditor's question: why did this
   autonomous run stop, and can I prove what it did? State the
   structural-difference hook. One scoping sentence: this is a CORA-conducted
   (closed-loop, semi-autonomous) alignment procedure; the agent-closed loop is
   future work. End with the contributions list. No figure.
2. **The auditor's tasks (~1 col), Figure 4.** Four tasks, each mapped to an
   event-log query and a visual encoding (T1 recover interrupted state; T2
   reproduce a decision via fold-to-version; T3 confirm convergence; T4 confirm
   the record is intact).
3. **The scrubber (~2 cols), Figure 1 (centerpiece) + Figure 2 inset.** Time
   axis, swim-lanes for setpoint/check/capture activities, nested iteration
   brackets colored by converged verdict, in-flight open intervals, draggable
   fold-to-version cursor; inset shows the fidelity badge at the scrub point.
4. **Crash recovery (~0.5 col), Figure 3.** A simulated mid-conduct crash
   leaves one in_flight activity with no outcome; the scrubber surfaces the
   exact step index as a gap.
5. **Substrate (~0.5 col), Figure 5.** The one capped architecture figure,
   labeled "substrate, not contribution"; immutability in one sentence.
6. **Related work (~0.75 col).** Drafted; see main.tex and
   related-work-map.md.
7. **Limitations and future work (~0.5 col).** Honest box (no shipped frontend;
   single beamline/scenario; no user study; agent-closed loop unbuilt; live
   streaming, run-to-run diff, deployed UI named not built).

## Figures (4 data : 1 architecture)

- F1 (data): the scrubber timeline (swim-lanes + nested brackets + cursor).
  Data ready: data/focus_run.json.
- F2 (data, inset on F1): fidelity badge at the cursor. Data ready (same file).
- F3 (data): crash-recovery in-flight gap. Needs a conductor-path export
  (pending; the append-path focus run has no in-flight markers).
- Table 1 (data/design): the task abstraction (task -> query -> encoding),
  authored in sections/tasks.tex (replaces the originally-planned "Figure 4").
- F5 (architecture): the provenance/event-record substrate; one figure only.

## Data export

DONE for F1/F2/Table 1: `data/focus_run.json`, derived from
`apps/api/tests/integration/scenarios/test_2bm_alignment_focus.py` (the
authoritative run definition; it asserts the rows round-trip through the real
Kernel and Postgres projections) via `data/build_run_data.py`. Twelve events,
thirteen activities, verdicts [F,F,F,T]; timestamps staggered synthetically.

This focus run is the append-path, so it carries NO in-flight markers. The
crash/in-flight data for F3 must come from the conductor path
(`test_conductor_against_softioc_postgres.py`), where a setpoint/action records
an in-flight marker before the outcome. That export is the next step.

The activities table has no GET route today; the export reuses the scenario's
direct SQL read shape (no new backend code needed for figures). Building a real
`GET /procedures/{id}/activities` read route is the roadmap-frontend step, not
required for the paper figures.

## Two-week build/write plan (deadline July 8 2026)

Writing runs parallel from day 1; hard feature-freeze at end of day 8.

- Days 1-2: export the run to JSON (reuse the scenario SQL); stagger timestamps.
- Days 3-4: fold-to-version helper (the one new piece) so the cursor yields
  folded state.
- Days 5-7: build F1, F3, and the F2 inset (static D3 / Plotly / matplotlib over
  the export); an interactive local HTML is an optional bonus for the talk.
- Days 8-9: F4 + F5; set up the VGTC two-column tex from the author kit.
- Days 10-12: write the five pages; write the limitations box first.
- Day 13: fact-check every repo claim against the tree; buffer.

Fallback if the export fights the test harness: hand-author a schema-faithful
fixture from the scenario assertions to unblock figures, backfill the real
export later.
