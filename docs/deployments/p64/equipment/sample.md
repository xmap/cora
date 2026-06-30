# Sample

*The sample-stage Assets at P64, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P64's experiment endstation carries the absorption-spectroscopy sample positioning, including a diamond-anvil-cell sub-stage for high-pressure XAS and NewFocus picomotor fine stages. The main bank is grouped (per-axis roles not labelled, `GROUP-1`).

- `SampleStage` binds `LinearStage`: the P64 sample / instrument motor bank (`exp_mot*` plus the `dac_*` high-pressure-cell sub-stage axes); per-axis roles grouped (`GROUP-1`).
- `PicomotorStage` binds `LinearStage`: the P64 NewFocus 8742 picomotor fine stages (`pico_mot01..04`); fine sample / optic alignment (`GROUP-1`).

## Families and confirmations

Both Assets bind the catalog `LinearStage` Family; P64 coins no new Family at the sample stage. The axis maps are read from the OnlineXML and carried confirm; the per-axis roles of the bank, the DAC high-pressure-cell control, and the picomotor assignments are not in the registry and are pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
