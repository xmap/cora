# Inventory

*The CORA Asset model for I20-1: the device tree read from the dodal commissioning module and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i20-1/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs (verified against `DiamondLightSource/dodal`, `src/dodal/beamlines/p51.py`). No vendor Model is bound. I20-1 introduces **no new catalog family**, and coins no loose family: the turbo slit reuses `Slit`, the PMAC `MotionController`, the PandA `TimingController`, the sample stage the graduated `Manipulator`, the Xspress3 the graduated `EnergyDispersiveSpectrometer`. This is a deliberately partial roster: the dispersive polychromator and strip detector that define EDE are not in source and are [open questions](questions.md) (POLY-1, STRIP-1), not modelled.

## The Asset tree

Root Asset `I20-1` (`tier = Unit`, `facility_code = diamond`); sub-systems nest below by `parent_id`.

| Asset | Family | PV (verified) | What it is |
| --- | --- | --- | --- |
| `I20-1` | (root) | `BL51P*` | bound to the Diamond Site |
| `Source` | InsertionDevice | (pending) | insertion-device source (absent from module) |
| `TurboSlit` | Slit | `BL51P-OP-PCHRO-01:TS:` | energy-selecting slit at the polychromator |
| `EnergyAxis` | PseudoAxis | (computed) | energy selected by the turbo-slit xfine |
| `SampleStage` | Manipulator | `BL51P-MO-STAGE-01:` | sample alignment stage (dodal mock) |
| `FluorescenceSpectrometer` | EnergyDispersiveSpectrometer | `BL51P-EA-DET-03:` | Xspress3 (dodal skip) |
| `Timing` | TimingController | `BL51P-EA-PANDA-02:` | PandA timing / sequencer (a pair) |
| `TurboSlitController` | MotionController | `BL51P-MO-STEP-06:` | PMAC trajectory controller (fly-scan) |

Every family is in the catalog; I20-1 coins none and binds no loose family. Notably the sample stage reuses the graduated `Manipulator` (the SIX / ESM precedent) and the Xspress3 reuses the graduated `EnergyDispersiveSpectrometer` (#345). The two devices the EDE technique actually turns on, the bent-crystal polychromator and the position-sensitive strip detector, are absent from the dodal module and are tracked as POLY-1 / STRIP-1, not modelled here.

## Pending confirmations

Every value below is read from dodal or inferred, awaiting the team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The bent-crystal polychromator (the EDE optic) | (not modelled) | `unknown-pending-confirmation` | (POLY-1) |
| The position-sensitive strip detector (EDE primary) | (not modelled) | `unknown-pending-confirmation` | (STRIP-1) |
| Insertion-device source / front-end / mirror | `Source` | `unknown-pending-confirmation` | (SRC-1) |
| PSS search-and-secure permit-leaf PVs | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Sample-stage axes and live PVs (dodal mock) | `SampleStage` | `unknown-pending-confirmation` | (STAGE-1) |
| Xspress3 live status (dodal skip) and flux chain | `FluorescenceSpectrometer` | `unknown-pending-confirmation` | (DET-1) |
| PMAC / PandA box firmware / IP | `TurboSlitController` / `Timing` | `unknown-pending-confirmation` | (DRIVE-1) |
