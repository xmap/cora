# Sample

*The sample-stage and sample-environment Assets across P07's experiment hutches, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P07 has two experiment hutches in this registry slice: the EH2 main hutch (the four-circle diffractometer plus the high-field magnet) and the EH2B secondary hutch (a sample bank). The motor banks are grouped (per-axis roles not labelled, `GROUP-1`).

## EH2: main experiment hutch

- `Goniometer` binds the catalog `Goniometer` Family: the four-circle Eulerian diffractometer (`e4cv`) + the two-theta arm (`twothetap07`); modelled as a `Goniometer` Asset, not the composed `Diffractometer` Assembly (`DIFF-1`).
- `SampleHexapod` binds `Hexapod`: the EH2 sample hexapod (`hx-hrz`); coarse sample positioning / orientation (`SAMPLE-1`).
- `Magnet` binds the allowlisted-loose `Magnet` Family: the EH2 17 T superconducting sample-environment magnet (`magnet17tf`), a further consumer of the 4-ID Family (`MAG-1`).
- `SampleEnvironment` binds `TemperatureController`: the EH2 Linkam T95 programmable temperature stage; in-situ heating / cooling (`TEMP-1`).
- `SampleStage` binds `LinearStage`: the EH2 sample / instrument motor bank (`exp33..64`); per-axis roles grouped (`GROUP-1`).
- `DetectorSlit` binds `Slit`: the EH2/EH3 detector / receiving slit (`g_eh3`, Galil DMC) (`OPT-1`).

## EH2B: secondary experiment hutch

- `SampleStage` binds `LinearStage`: the EH2B sample / instrument motor bank (`exp01..64`); per-axis roles grouped (`GROUP-1`).

## Families and confirmations

Every Asset here binds an existing Family: `Goniometer` for the diffractometer, `Hexapod` for the hexapod, the allowlisted-loose `Magnet` for the 17 T magnet, `TemperatureController` for the Linkam, `LinearStage` for the banks, `Slit` for the detector slit. P07 coins no new Family. The axis maps are read from the OnlineXML and carried confirm; the diffractometer circle count, the magnet field, and the per-axis bank roles are pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
