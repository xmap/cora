# Figure data

Run data backing the paper's figures. Committed (it is figure input, not a build
artifact).

## `lights_out_run.json`

One lights-out, agent-supervised run at APS 2-BM: the single run all the figures
are drawn from. CORA conducts a rotation-axis centering alignment (a
four-iteration peak-bracket search on `SampleTop_X` that converges), the science
scan begins and its third projection is in flight when the beam drops, the
RunSupervisor agent holds the run and auto-resumes it when the beam returns, the
fly-scan is restarted, the scan finishes, and the collected dataset is written to
disk before the run completes.

**Provenance.** Values mirror the passing integration scenario
[`apps/api/tests/integration/scenarios/test_2bm_lights_out_supervised_alignment.py`](../../../apps/api/tests/integration/scenarios/test_2bm_lights_out_supervised_alignment.py),
which produces exactly these activities, iteration verdicts, run-lifecycle
events, and the supervisor Resume Decision against a real Kernel + Postgres.
Regenerate with `python3 data/build_lights_out_data.py`.

**What it contains.**
- `run.events`: the four-beat lifecycle `RunStarted` (operator), `RunHeld`
  (RunSupervisor), `RunResumed` (RunSupervisor, carrying a Resume Decision),
  `RunCompleted` (operator) with per-event `by`/`role`.
- `iterations`: four centering passes with verdicts `[false, false, false, true]`
  and the center-of-rotation residual falling 2.00 -> 1.05 -> 1.40 -> 0.30 px,
  bracketed in [0.040, 0.080] mm and bisected to 0.060 mm.
- `activities`: setpoint / acquire / check per pass, the lock setpoint, the
  fly-scan rotation setpoint, the fly-scan setup (taxi + PSO arm, before the
  first frame and again on the restart), six science projections (two complete,
  the third in flight at the beam loss), the re-acquired third projection plus
  the rest of the scan, and the data save (write the dataset to HDF5/DXfile).
- `provenance.cursor_at` / `beam_loss_at` / `beam_back_at`: the audit instant and
  the hold window the figures use.

**Caveats.** The `sampled_at` and event times are staggered synthetically and
compressed for a readable axis; the scenario records one logical instant, and the
overnight hold (which can last tens of minutes) is illustrative, not measured.

## Regenerating from a live run (optional, authoritative)

`build_lights_out_data.py` mirrors the scenario's literal values for
reproducibility without a database. To export from a live run instead, add a
JSON dump to the scenario test after its assertions (it already reads the run,
procedure, and activity rows) and run it against the integration test stack
(testcontainers Postgres). Mind the known hazards: name-derived stream-seed 409s,
`pool=None` short-circuits, and projection-drain timing.
