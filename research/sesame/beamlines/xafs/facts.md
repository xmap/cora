# Extracted facts: XAFS/XRF (BM08)

Candidate device facts for `xafs` (SESAME BM08, X-ray Absorption Fine Structure / X-ray Fluorescence spectroscopy). Candidates only; confirm every row before modeling. Source: the public `SESAME-Synchrotron/XAFSScanTool` + `xafs-dt8824-daq` repos (read 2026-06). Every value is carried `confirm` until SESAME staff verify it: the facility DAQ repo is strong evidence, not a CORA-owned fact.

!!! note "EPICS prefix + dynamic PVs"
    The XAFS ScanTool is Python over EPICS with a `P` prefix `XAFS:`. Some device PVs are built dynamically (f-string fragments like `ACQ::`, `ThetaSpeed::`, `FicusIntTimeDic:` appear in source as templates), so only the literal, verbatim PV roots are recorded below; the dynamic ones are noted as confirm-pending. The DT8824 DAQ (a Measurement Computing module) has its own EPICS driver repo (`xafs-dt8824-daq`) for the ion-chamber readout.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV (verbatim from source), role/class as sub-detail. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV (verbatim) | source/class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| Monochromator | Monochromator | `BLSetup:Crystal` (crystal selection) | Mono.py | source | yes |
| EnergyCalibration | PseudoAxis (?) | `ENGCAL:FoilElement`, `ENGCAL:RealFoilEng` | Mono.py (energy-to-foil calibration) | source | yes |
| SampleStage | LinearStage | `SMP:X`, `SMP:Y` | common.py | sample | yes |
| FicusDetector | EnergyDispersiveSpectrometer | `Ficus:` (Erase/Start/ROIs/FrameDuration/DetectorTemp...) | detectors/ficus.py (FICUS SDD) | detection | yes |
| SDDDetector | EnergyDispersiveSpectrometer | `SDD2:` (getFrameDuration) | detectors | detection | yes |
| IonChamber | FluxMonitor (?) | (IC class; DT8824 DAQ, dynamic ACQ:: PVs) | detectors/ic.py + xafs-dt8824-daq | detection | yes (PV dynamic) |

Device-level handles read verbatim from source: `BLSetup:Crystal`, `ENGCAL:FoilElement`/`ENGCAL:RealFoilEng`, `SMP:X`/`SMP:Y`, the `Ficus:` SDD control block, `SDD2:`. The ion-chamber PVs are built dynamically in `ic.py` and read via the `xafs-dt8824-daq` EPICS driver; the literal channel handles need staff confirmation (PV-dynamic).

## Role hints

- **Positioner**: the sample stage (X/Y); the mono crystal selection.
- **Sensor**: ion chamber (transmission I0/I1, via the DT8824 DAQ), energy-calibration foil readback.
- **Detector**: FICUS SDD + SDD2 (energy-dispersive fluorescence for XRF / fluorescence-XAS).
- **Energy scan**: `Mono.py` drives the energy scan; `ENGCAL` ties the mono angle to a real foil-edge energy. This is a scanning-XAS energy axis (relevant to the pending energy_scan Capability question, see recurrence).

## Trust hints

Facility-org EPICS DAQ + ScanTool; no queue-server (the ScanTool is the orchestration). EPICS-Qt GUI (`qeframework`). The ScanTool is the layer CORA's EdgeConductor would conduct over.

## New-family watch

No new coining:
- **Ficus / SDD2 -> EnergyDispersiveSpectrometer** (graduated): two SDD energy-dispersive detectors for XRF/fluorescence-XAS; bind directly. (FICUS is a SESAME/in-house SDD readout; same family as Xspress3/Vortex/DXP elsewhere.)
- **BLSetup:Crystal -> Monochromator** (graduated): the mono crystal selection.
- **IonChamber -> FluxMonitor (?)** (graduated): the transmission I0/I1; confirm the DT8824 channel binding.
- **SMP stage -> LinearStage** (graduated).
- **EnergyCalibration -> PseudoAxis (?)**: the ENGCAL energy-to-foil mapping is a pseudo-axis / calibration device, not a physical stage; confirm.

## Deferred / absent

- **OPTICS-1:** the physical DCM crystal/angle motors, mirrors, slits are not literal in the ScanTool (it drives the mono via `BLSetup`/`Mono.py` abstractions); confirm the mono device PVs with staff.
- **PV-dynamic:** ion-chamber and several scan-control PVs are built dynamically; the literal handles need staff confirmation.
- PSS / hutch safety and passive beam-path tier not in the DAQ repo (SCOPE-1).
