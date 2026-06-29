# Sample

*The sample-stage Assets at P08, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P08's experiment endstation centres on a six-circle Kohzu diffractometer with a sample hexapod. The diffractometer circles plus sample positioning are exposed as a generically-named `diff*` motor bank, grouped as the goniometer / sample stage carrying the handles, per-axis roles pending (`GROUP-1`).

- `Goniometer` binds the catalog `Goniometer` Family: the six-circle Kohzu diffractometer (`kozhue6cctrl` driving the `diff1..N` bank); modelled as a `Goniometer` Asset, not the composed `Diffractometer` Assembly (`DIFF-1`, `GROUP-1`).
- `SampleHexapod` binds `Hexapod`: the experiment sample hexapod (`hx-hrz`); coarse sample positioning / orientation (`SAMPLE-1`).

## Families and confirmations

Both Assets bind existing catalog Families (`Goniometer`, `Hexapod`); P08 coins no new Family at the sample stage. The axis maps are read from the OnlineXML and carried confirm; the six-circle geometry, the per-axis roles of the `diff*` bank, and the sample-environment detail are not fully labelled in the registry and are pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
