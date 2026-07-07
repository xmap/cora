# Figure data

Run data backing the paper's figures. Committed (it is figure input, not a build
artifact).

## `lights_out_run.json`

One robot-loaded, lights-out session at APS 2-BM: a sample-changing robot loads
two samples in turn, under one Campaign, and all the figures are drawn from it.
For each sample the robot mounts it onto the rotary stage, CORA conducts a
rotation-axis centering alignment (a four-iteration peak-bracket search on
`SampleTop_X` that converges), the science scan runs, and the robot dismounts it.
On the second sample the beam drops while the third projection is in flight, the
RunSupervisor agent holds the run and auto-resumes it when the beam returns, the
fly-scan is restarted, the scan finishes, and the collected dataset is written to
disk before the run completes.

**Provenance.** Values mirror the passing integration scenario
[`apps/api/tests/integration/scenarios/test_2bm_robot_lights_out_two_sample.py`](../../../apps/api/tests/integration/scenarios/test_2bm_robot_lights_out_two_sample.py),
which produces these activities, iteration verdicts, run-lifecycle events, the
robot mount/dismount custody events, and the supervisor Resume Decision against a
real Kernel + Postgres. Regenerate with `python3 data/build_lights_out_data.py`.

**Scope (modeled vs. deployed).** The sample-change hardware at 2-BM (a UR3e arm
with its own EPICS control) is deployed and has executed mount/dismount cycles
with a beamline handshake; tomoscan is PV-scriptable. CORA's orchestration of the
robot is modeled in the scenario, played through the same real event store as the
rest of the run; the supervisor decision layer beyond hold/resume (FOV-fit and
lens-change branches, per-sample recentering as a supervised decision) is out of
scope. See the paper's Limitations section.

**What it contains.**
- `robot.events`: the four robot custody events, `mount` / `dismount` per sample,
  attributed to the Manipulator sample-changer Asset.
- `samples`: the two samples with their `mount_at` / `dismount_at` custody window.
- `runs`: two run lifecycles, sample A `RunStarted` -> `RunCompleted` (a clean
  run) and sample B `RunStarted` -> `RunHeld` -> `RunResumed` -> `RunCompleted`
  (the RunSupervisor holds and resumes on beam loss, carrying a Resume Decision),
  each with per-event `by`/`role`.
- `iterations`: four centering passes per sample with verdicts
  `[false, false, false, true]`; sample A converges at a different center than
  sample B (each sample's position relative to the fixed rotation axis).
- `activities`: per sample, setpoint / acquire / check per pass, the lock
  setpoint, the fly-scan rotation setpoint, the fly-scan setup (taxi + PSO arm),
  the science projections (sample B's third is in flight at the beam loss and is
  re-acquired after resume), and the data save.
- `provenance.cursor_at` / `beam_loss_at` / `beam_back_at`: the audit instant and
  the hold window the figures use (on sample B's scan).

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
