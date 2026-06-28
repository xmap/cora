# Sample

*How SYRMEP holds and rotates the specimen: a heavy-payload rotation stage on a five-axis sample positioner. First cut, reverse-engineered.*

The sample station is where tomography happens: the specimen rotates about the vertical axis while the detector records projections. SYRMEP is notable for a heavy-payload rotator that handles large specimens (up to 120 kg), which is what enables its large-specimen and clinical work.

## The rotation stage

`Rotary` binds the catalog [`RotaryStage`](../../../catalog/families.md) Family: the tomographic rotation axis (theta), the same Family the 2-BM, FXI, and 7-BM imaging beamlines bind for their rotation. The documented heavy-payload rotator carries up to 120 kg at 1-20 deg/s with 0.02 deg precision (J. Synchrotron Rad. 2023). Whether a separate standard-payload rotation stage is also installed, its range and bearing, and the wobble spec are pending (`STAGE-1`).

Continuous (fly) and helical scans run as the rotation stage's trigger-driven sweep under the DonkiOrchestra scan engine; the hardware trigger source is part of the control plane CORA carries confirm-pending (`CTRL-1`).

## The sample positioner

`SampleStage` binds [`LinearStage`](../../../catalog/families.md): the five-axis sample-positioning stage, used to centre and translate the specimen on the rotation axis. The motor vendors, the micro-positioning resolution, and the per-axis map and handles are pending (`SAMPLE-1`).

## Pending

| Value to confirm | Applies to | Tracking |
| --- | --- | --- |
| Standard rotation stage range / bearing / model and the wobble spec (beyond the heavy rotator) | `Rotary` | `STAGE-1` |
| The five-axis sample-positioner motor vendors, resolution, axis map, and handles | `SampleStage` | `SAMPLE-1` |
| The projection trigger source for continuous / fly scans | `Rotary` | `CTRL-1` |
