# Sample

*The sample-stage and focusing Assets across P10's experiment areas, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P10 has three experiment areas sharing the coherent beam: E1 (coherent imaging), E2 (XPCS / diffraction, with the LCX piezo sub-station), and LAB (offline). The dense sample positioning at E1 and E2 is exposed as generically-named motor banks (`E1_MOT01..97`, `E2_MOT01..96`), grouped as stage Assets carrying the bank prefix, per-axis roles pending (`GROUP-1`).

## E1: coherent imaging

- `Hexapod` binds `Hexapod`: the E1 six-axis hexapod (`HEXAX-HEXARZ`); coarse sample orientation.
- `CompoundRefractiveLens` binds `Transfocator`: the E1 CRL box (`EHCRL`, lensesbox); the coherent-beam focusing (`OPT-1`).
- `GuardSlit` binds `Slit`: the E1 guard slit (`G1`, Galil DMC slit controller); the coherence-defining slit (`OPT-1`).
- `SampleStage` binds `LinearStage`: the E1 sample / instrument motor bank (`E1_MOT01..97`, including the `e6cctrl` six-circle diffractometer controller); per-axis roles grouped (`GROUP-1`).
- `SampleVirtualStages` binds `PseudoAxis`: the E1 virtual / coupled axes (`vm_e1_*`).

## E2: XPCS / diffraction

- `Mirrors` binds `Mirror`: the E2 mirror stages (`mirror1` / `mirror2` y / rz plus `mirrorz`, spk controllers); the focusing / steering mirrors (`OPT-1`).
- `SamplePiezo` binds `LinearStage`: the E2 SmarAct sample piezos (`SPX / SPY / SPZ`); fine sample positioning for XPCS (`SAMPLE-1`).
- `TwoThetaArm` binds `RotaryStage`: the E2 two-theta detector arm (`eh2tthp10`); the scattering-angle axis for coherent diffraction (`SAMPLE-1`).
- `GuardSlit` binds `Slit`: the E2 guard slit (`G2`, Galil DMC slit controller) (`OPT-1`).
- `SampleStage` binds `LinearStage`: the E2 sample / instrument motor bank (`E2_MOT01..96`); per-axis roles grouped (`GROUP-1`).
- `SampleVirtualStages` binds `PseudoAxis`: the E2 virtual / coupled axes (`vm_e2_*`).

## LCX: piezo sub-station (within E2)

- `NanoPositioner` binds `LinearStage`: the LCX AttoCube (`APINY / APINZ`) and SmarAct (`SPX / SPY / SPZ`) nano-positioning piezos; the coherent-imaging sample sub-stage (`LCX-1`, `SAMPLE-1`).

## LAB: offline

- `SimulatedDiffractometer` binds `Goniometer`: the LAB simulated six-circle (E6C) diffractometer (`e6cctrl_simu` + `chi / delta / gamma / mu / omega / phi` simulation axes); offline alignment / testing (`LAB-1`).

## Families and confirmations

Every Asset here binds an existing catalog Family (`Hexapod`, `Transfocator`, `Slit`, `LinearStage`, `Mirror`, `RotaryStage`, `PseudoAxis`, `Goniometer`); P10 coins none at the sample stage. The axis maps are read from the OnlineXML and carried confirm; the per-axis roles of the motor banks, the CRL focal sizes, and the diffractometer geometry are not in the registry and are pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
