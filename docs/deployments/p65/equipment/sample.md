# Sample

*The sample-stage Assets at P65, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P65's experiment endstation carries the applied-XAS sample positioning: a sample / instrument motor bank, a beam-defining slit, and an instrument table. The bank is grouped (per-axis roles not labelled, `GROUP-1`).

- `SampleStage` binds `LinearStage`: the P65 experiment sample / instrument motor bank (`a2_mot01..20`); per-axis roles grouped (`GROUP-1`). The `a2_dmy*` stubs are dummy / placeholder devices, noted not modelled (`STUB-1`).
- `ExperimentSlit` binds `Slit`: the P65 experiment slit (`eh_slit` center x / y, vmexecutor virtual axes).
- `ExperimentTable` binds `Table`: the P65 experiment table (`eh_table` height / vertical, vmexecutor virtual axes).

## Families and confirmations

Every Asset here binds an existing catalog Family (`LinearStage`, `Slit`, `Table`); P65 coins no new Family. The axis maps are read from the OnlineXML and carried confirm; the per-axis roles of the sample bank, and the sample-environment / sample-changer detail (not in the registry), are pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
