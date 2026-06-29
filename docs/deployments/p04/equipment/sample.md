# Sample

*The sample-stage Assets across P04's two experiment endstations, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P04 has two experiment endstations, EXP1 and EXP2, each with its own sample positioning. The registry exposes the positioning as generically-named motor banks rather than labelled axes, so the stages are grouped as `Manipulator` Assets carrying the Tango handles, every per-axis role pending (`GROUP-1`).

## EXP1

- `SampleManipulator` binds `Manipulator`: the EXP1 sample manipulator motor bank (`exp1_mot01..16`). Sixteen axes, roles not labelled in the registry, grouped as one Asset (`GROUP-1`).
- `SecondaryPositioner` binds `Manipulator`: the EXP1 secondary positioner bank (`ps2.01..14`). Fourteen axes, roles not labelled (`GROUP-1`).
- `ViewCamera` binds `Camera`: the EXP1 viewing camera (Prosilica / Allied Vision) for sample viewing (`DET-1`).

## EXP2

- `ExitShutterUnit` binds `Slit`: the EXP2 exit-shutter / diagnostic unit (`EXSU2`: slit, translation, beam-position monitor, baffle). Modelled as a beam-defining `Slit`; the bpm / baffle roles are `EXSU-1`.
- `ExperimentPositioner` binds `Manipulator`: the EXP2 generic positioner axes (`exp2_mot06`, `exp2_mot08`); roles not labelled (`GROUP-1`).
- `VirtualPositioners` binds `PseudoAxis`: the EXP2 virtual position axes (`vm_ps_position`, `vm_screen_position`) coupling the positioner and screen motions (`GROUP-1`).

## Families and confirmations

Every Asset here binds an existing catalog Family (`Manipulator`, `Camera`, `Slit`, `PseudoAxis`); P04 coins none at the sample stage. The axis maps are read from the OnlineXML and carried confirm; the per-axis roles of the motor banks, and the `EXSU2` sub-roles, are not in the registry and are pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
