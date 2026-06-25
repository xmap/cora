# Figure data

Run data backing the paper's figures. Committed (it is figure input, not a build
artifact).

## `focus_run.json`

The CORA-conducted autofocus alignment at APS 2-BM (SampleTop_Z, a
four-iteration peak-bracket search): the centerpiece run for Figure 1, the
fidelity-badge inset (Figure 2), and the Section 3 walkthrough.

**Provenance.** Values mirror the authoritative run definition in
[`apps/api/tests/integration/scenarios/test_2bm_alignment_focus.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_focus.py),
which asserts these exact activities and iterations round-trip through the real
Kernel and the Postgres projections (`entries_operation_procedure_activities`,
`proj_operation_procedure_iterations`). Regenerate with
`python3 data/build_run_data.py`.

**What it contains.** 12 procedure events, 13 activities (setpoint / action /
check across 4 iterations, plus a final lock setpoint), and 4 iteration verdicts
`[false, false, false, true]`. Focus positions 0.000, 0.500, 1.000, 0.750 mm;
image sharpness 0.50, 0.70, 0.65, 0.74; peak bracketed in [0.500, 1.000] mm,
bisected and locked at 0.750 mm.

**Caveats.** This is the clean, completed run on the `append_activities` path, so
it carries no in-flight markers (`result` is null on every activity). The
`sampled_at` times are staggered synthetically for a readable axis; the source
scenario records a single logical instant, so wall-clock spacing is not real.

## `crash_run.json` (Figure 3)

A CORA-conducted run on the **conductor** path, truncated to simulate a crash:
the backing data for Figure 3. The conductor records a `result="in_flight"`
marker before each side-effecting setpoint or action and the outcome after (see
`apps/api/src/cora/operation/conductor.py`, "Pre-effect in-flight marker"; the
payload carries `step_index` + `result` per the `{**body, step_index, result}`
append). Truncating after the final marker leaves an in-flight entry with no
matching outcome at one step index, the interrupted step.

**Provenance.** Conductor-path activity shapes and values come from
[`apps/api/tests/integration/test_conductor_against_softioc_postgres.py`](../../../apps/api/tests/integration/test_conductor_against_softioc_postgres.py)
(real softIOC + Postgres). Only the truncation (the crash) is constructed.
Regenerate with `python3 data/build_crash_data.py`.

**What it contains.** Four activity rows: setpoint marker + outcome (step 0,
completed), check (step 1, completed), setpoint marker (step 2, dangling, no
outcome); `interrupted_step_index = 2`. Channel names are the softIOC test
channels with the per-test prefix omitted.

## Regenerating from a live run (optional, authoritative)

`build_run_data.py` mirrors the scenario's literal values for reproducibility
without a database. To export from a live run instead, add a JSON dump to the
scenario test after its assertions (it already reads the rows via SQL) and run
it against the integration test stack (testcontainers Postgres). Mind the known
hazards: name-derived stream-seed 409s, `pool=None` short-circuits, and
projection-drain timing.
