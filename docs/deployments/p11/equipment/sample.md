# Sample

*The experiment-hutch positioning and sample-environment Assets at P11, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P11's experiment hutch carries the macromolecular-crystallography sample environment: a goniometer (cryostream-cooled) for rotation MX. The registry does not label the goniometer or the individual sample instruments; it exposes the experiment-hutch motions as area-grouped motor banks (`eh1`, `eh2`, `eh3`, the piezo bank), so these are grouped as positioning stages carrying the bank prefix, with the MX instrument structure carried as a question (`MX-1`, `GROUP-1`).

## Experiment-hutch positioning

- `ExperimentStage1` binds `LinearStage`: the eh1 motor bank (`eh1_mot06..16`); experiment-hutch positioning, roles not labelled (`GROUP-1`, `MX-1`).
- `ExperimentStage2` binds `LinearStage`: the eh2 motor bank (`eh2_mot01..16`) (`GROUP-1`, `MX-1`).
- `ExperimentStage3` binds `LinearStage`: the eh3 motor bank (`eh3_mot01..16`) (`GROUP-1`, `MX-1`).
- `PiezoStage` binds `LinearStage`: the experiment-hutch piezo bank (`ehpm3_mot01..16` on `p11/piezomotor`); fine sample / instrument positioning (`GROUP-1`).
- `ServoStage` binds `LinearStage`: the eh1 servo motor (`eh1_srv01`); a continuous / high-speed axis (likely the goniometer omega or a fast shutter), role pending (`GROUP-1`).

## Sample environment

- `SampleTemperature` binds the graduated `TemperatureController`: the experiment-hutch Oxford Cryostream 700 (`eh_cryo01`); the MX cryocooling (`TEMP-1`).

## Families and confirmations

Every Asset here binds an existing catalog Family (`LinearStage`, `TemperatureController`); P11 coins none. The axis maps are read from the OnlineXML and carried confirm; the goniometer geometry, the MX-specific instrument breakdown, and the per-axis roles of the banks are not in the registry and are pending (`MX-1`, `GROUP-1`). The automated sample changer, if present, is not in the registry and would be a deferred sample-exchange Procedure, not a device (`ROBOT-1`). See [Open questions](../questions.md) and the [Inventory](../inventory.md).
