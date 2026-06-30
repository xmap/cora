# Sample

*The sample-stage Assets at P22, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P22's HAXPS experiment endstation carries the photoemission sample manipulator: the sample positioning for hard X-ray photoelectron spectroscopy. It is exposed as a generically-named motor bank, grouped as one `Manipulator` Asset carrying the handles, per-axis roles pending (`GROUP-1`).

- `SampleStage` binds `Manipulator`: the HAXPS sample / instrument motor bank (the `p22/motor` experiment bank); the photoemission sample manipulator, per-axis roles grouped (`GROUP-1`). The `haxps_dmy*` stubs are dummy / placeholder devices, noted not modelled (`STUB-1`).

## Families and confirmations

The sample stage binds the catalog `Manipulator` Family (the photoemission-manipulator Family graduated at NSLS-II ESM); P22 coins no new Family at the sample stage. The axis map is read from the OnlineXML and carried confirm; the per-axis roles (the manipulator's polar / azimuthal / translation axes), and the sample-environment detail, are not labelled in the registry and are pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
