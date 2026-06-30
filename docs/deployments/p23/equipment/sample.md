# Sample

*The sample-stage Assets at P23, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P23's experiment positioning is exposed as one large generic motor bank, grouped as the experiment stage carrying the handles, per-axis roles pending (`GROUP-1`). The optics, diffractometer, and sample positioning are not individually distinguished in the registry slice.

- `ExperimentStage` binds `LinearStage`: the P23 experiment / instrument motor bank (`eh_mot*` on the `hasep23oh` host, ~79 axes), the in-situ diffraction sample positioning, diffractometer, and optics motions; per-axis roles grouped (`GROUP-1`, `OPT-1`, `DIFF-1`).
- `DevStage` binds `LinearStage`: a single device-development / test axis on the `hasep23dev` host; a dev / commissioning stage (`STUB-1`).

## Families and confirmations

Both stages bind the catalog `LinearStage` Family; P23 coins no new Family. The axis map is read from the OnlineXML and carried confirm; the per-axis roles of the bank, the diffractometer geometry, the optics breakdown, and the in-situ sample environments are not labelled in the registry and are pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
