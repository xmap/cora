# Sample

*The sample-stage and focusing Assets across P06's two scanning-probe endstations, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P06 has two scanning-probe endstations, the micro-probe (MC01) and the nano-probe (NC1), each a dense stack of coarse positioning (hexapods), focusing (KB lens stages), and fine scanning (piezo and Aerotech stages). The large motor banks (`mi_mot01..84` at MC01, `nat_mot01..32` at NC1) carry the bulk of the endstation positioning but are not labelled per axis, so they are grouped as stage Assets carrying the bank prefix, every per-axis role pending (`GROUP-1`).

## MC01: micro-probe

- `Hexapod` binds `Hexapod`: the MC01 six-axis hexapod (`hexx-hexz` translations, `hexu-hexw` rotations); coarse sample orientation.
- `SampleStage` binds `LinearStage`: the MC01 sample-positioning stack, the `mi_mot` bank (46 axes) plus the MMC, PI-piezo, and SMC-Hydra fine stages; per-axis roles grouped (`GROUP-1`).
- `ScanStage` binds `LinearStage`: the MC01 Aerotech scanning stage (`scanx / scany / scanz`); the continuous fly-scan raster axes for scanning microscopy (`SCAN-1`).
- `PinAlignment` binds `LinearStage`: the MC01 pin / sample alignment SmarAct piezos.
- `VirtualStages` binds `PseudoAxis`: the MC01 virtual coupled axes (sample rotation, detector, fluo-detector positioning) (`GROUP-1`).
- `QuadrantBPM` binds `FluxMonitor`: the MC01 quadrant beam-position monitor (i404).

## NC1: nano-probe

- `KBLensHexapodHorizontal` and `KBLensHexapodVertical` bind `Hexapod`: the two SmarAct hexapods carrying the horizontal- and vertical-focusing KB mirrors / lenses (nine axes each: translations, pushers, rotations) (`OPT-1`).
- `LensFineStages` binds `PseudoAxis`: the NC1 KB-lens virtual fine-positioning axes (`hlens* / vlens*`), coupling the hexapod motions (`OPT-1`).
- `SamplePiezo` binds `LinearStage`: the NC1 SmarAct sample / phase / interferometer piezos (`phase*`, `ints*`, `pin*`) (`SAMPLE-1`).
- `SampleRotation` binds `RotaryStage`: the NC1 sample rotation (`samr`, Pegasus motor); the nano-tomography rotation axis (`SAMPLE-1`).
- `CentringPiezo` binds `LinearStage`: the NC1 sample-centring piezos (PI E-871).
- `ScanStage` binds `LinearStage`: the NC1 Aerotech scanning stage (`scanu / scanv / scanz`) plus virtual `scanx / scany`; the fly-scan raster axes (`SCAN-1`).
- `NanoPositioningStage` binds `LinearStage`: the NC1 nano-positioning motor bank (`nat_mot`, 20 axes); per-axis roles grouped (`GROUP-1`).
- `NC1Slits` binds `Slit`: the NC1 defining slit (virtual h/v gap and offset).

## Families and confirmations

Every Asset here binds an existing catalog Family (`Hexapod`, `LinearStage`, `RotaryStage`, `PseudoAxis`, `Slit`, `FluxMonitor`); P06 coins none at the sample stage. The axis maps are read from the OnlineXML and carried confirm; the per-axis roles of the motor banks, the KB focal sizes, and the scan-stage fly-scan parameters are not in the registry and are pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
