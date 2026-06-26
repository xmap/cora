# Sample

*The sample alignment stage. PVs verified against dodal `src/dodal/beamlines/p51.py`.*

EDE puts the sample in the dispersed beam and follows its absorption spectrum in time; the sample side in the commissioning module is just the alignment stage.

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `SampleStage` | Manipulator | `BL51P-MO-STAGE-01:` | aligns the sample in the dispersed beam (X / Y) |

## The sample stage

The `SampleStage` is the alignment stage (`alignment_x` / `alignment_y`). It reuses the graduated `Manipulator` family, the multi-axis sample-positioning family the soft-X-ray beamlines SIX and ESM earned; a two-axis alignment stage is a thin instance of it.

The honest caveat is that the dodal module currently constructs this stage as a **mock** device (`mock=True`), with a source comment that the motors are being reconnected on the beamline. So the PVs (`BL51P-MO-STAGE-01:X` / `Y`) are real but not yet connected; CORA carries them `confirm` and tracks the reconnection and the full axis set as STAGE-1. A time-resolved EDE experiment also wants an in-situ sample environment (a reaction cell, a flow / temperature stage) to drive the dynamics the dispersive detector captures; none is in the commissioning module, so it is left to a later cut.
