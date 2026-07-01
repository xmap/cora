# Sample

*The sample-stage Assets at P61, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P61's experiment positioning is exposed as one large generic motor bank, grouped as the experiment stage carrying the handles, per-axis roles pending (`GROUP-1`). The Large Volume Press (P61A) and the source are not exposed in the registry slice.

- `ExperimentStage` binds `LinearStage`: the P61 experiment / instrument motor bank (`eh_mot*` on the `hasnp61eh2` host, ~64 axes), the high-energy white-beam sample positioning and diffractometer motions; per-axis roles grouped (`GROUP-1`).

## Families and confirmations

The experiment stage binds the catalog `LinearStage` Family; P61 coins no new Family. The axis map is read from the OnlineXML and carried confirm; the per-axis roles of the bank, the Large Volume Press (which would reuse the catalog `PressureCell` Family when exposed, `PRESS-1`), and the sample-environment detail are not in the registry and are pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
