# Sample

*The sample-stage Assets across P24's two experiment hutches, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P24's sample positioning is exposed as generically-named motor banks per hutch, grouped as stage Assets carrying the bank prefix, per-axis roles pending (`GROUP-1`). The chemical-crystallography diffractometer is not individually labelled in the registry.

## EH2: main experiment hutch

- `SampleStage` binds `LinearStage`: the EH2 diffractometer / sample motor bank (`mot01..40`); the chemical-crystallography diffractometer and sample positioning, per-axis roles grouped (`GROUP-1`, `DIFF-1`).
- `CoupledAxes` binds `PseudoAxis`: the EH2 coupled / virtual axes (`eh2_vm*` on vmexecutor) (`GROUP-1`).

## EH1: experiment hutch

- `SampleStage` binds `LinearStage`: the EH1 sample / instrument motor bank (~16 axes); per-axis roles grouped (`GROUP-1`).

## Families and confirmations

The sample stages bind the catalog `LinearStage` Family and the coupled axes `PseudoAxis`; P24 coins no new Family at the sample stage. The axis maps are read from the OnlineXML and carried confirm; the diffractometer geometry (whether it warrants a `Goniometer` or `Diffractometer` binding once labelled), the per-axis bank roles, and the sample-environment detail are not in the registry and are pending. The `eh2_dmy*` stubs are dummy / placeholder devices, noted not modelled (`STUB-1`). See [Open questions](../questions.md) and the [Inventory](../inventory.md).
