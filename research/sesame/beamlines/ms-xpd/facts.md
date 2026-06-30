# Extracted facts: MS/XPD (ID09)

Candidate device facts for `ms-xpd` (SESAME ID09, Materials Science / X-ray Powder Diffraction). Candidates only; confirm every row before modeling. Source: the public `SESAME-Synchrotron/MS-XPD-ScanTool` repo (read 2026-06). Every value is carried `confirm` until SESAME staff verify it: the facility DAQ repo is strong evidence, not a CORA-owned fact.

!!! note "EPICS prefix MS:"
    The MS/XPD ScanTool drives a theta / two-theta diffractometer with an area detector, over EPICS with a `P` prefix `MS:`. Device records carry a readable location-function code: `ES-DIFF-STP-ROTX1` = EndStation DIFFractometer STepPer ROTation aXis 1. The scan modes are two-theta step, theta/two-theta+slits step, and a temperature scan.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV (verbatim from source), role as sub-detail. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV (verbatim) | source | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| Diffractometer | Diffractometer (?) | `MC1:ES-DIFF-STP-ROTX1`, `ROTX2`, `ROTX3` (theta / 2theta / detector arm) | MC1 motion controller | sample | yes |
| DiffractometerAux | RotaryStage | `MC3:ES-DIFF-STP-ROTX2` (+ `.VELO`) | MC3 motion controller | sample | yes |
| AreaDetector | Camera | `CAM1:` (acquire/setExpTime/setNImages/setImgPath) | detectors | detection | yes |
| FrontEndShutter | Shutter | `SHUTTER1:Status`, `SHUTTER2:Status` | common | source | yes |
| BeamStopper | Shutter (?) | `STOPPER:Status` | common | source | yes |
| RingCurrent | GenericProbe (?) | `DCCT1:getDcctCurrent` | diagnostics (machine) | source | yes |
| BeamEnergy | GenericProbe (?) | `DI:getBeamEnergy` | diagnostics | source | yes |
| PhotonShutterStatus | Shutter (?) | `PSH:getStatus`, `PHST:getStatus` | common | source | yes |

Device-level handles read verbatim from source: the `MC1:ES-DIFF-STP-ROTX1/2/3` + `MC3:ES-DIFF-STP-ROTX2` diffractometer rotation axes, `CAM1:` area-detector control block, `SHUTTER1/2:Status`, `STOPPER:Status`, `DCCT1:getDcctCurrent`, `DI:getBeamEnergy`.

## Role hints

- **Positioner**: the diffractometer rotation axes (theta / two-theta / detector arm) on MC1 + MC3 motion controllers.
- **Sensor**: ring current (DCCT), beam energy (DI), shutter/stopper status.
- **Detector**: CAM1 (the powder-diffraction area detector).

## Trust hints

Facility-org EPICS DAQ + ScanTool; no queue-server. EPICS-Qt GUI. The ScanTool (the two-theta / theta-two-theta scan plans) is the orchestration layer CORA's EdgeConductor would conduct over.

## New-family watch

No new coining, but one graduation-relevant note:
- **Diffractometer (?)**: the MC1 `ES-DIFF-STP-ROTX1/2/3` axes are a theta / two-theta (+ detector arm) diffractometer. Per the fleet-wide Diffractometer question (NSLS-II has it loose/Assembly at n=6, contested contract), this is another consumer to fold into that review: is SESAME MS a true multi-circle diffractometer (graduate / Assembly) or a 2-3-axis powder stage (RotaryStage composition)? Read as a powder diffractometer (theta/2theta), it leans toward the RotaryStage-composition / Assembly reading. Do NOT coin here.
- **CAM1 -> Camera** (graduated), **SHUTTER/STOPPER/PSH -> Shutter** (graduated, confirm the stopper vs a beam-stop), **DCCT/DI -> GenericProbe (loose)** (machine diagnostics).

## Deferred / absent

- **OPTICS-1:** the DCM / mono, mirrors, and primary slits are not in the ScanTool (it is diffractometer + detector focused); the "slits" scan mode uses the same MC controllers, the slit blades' own PVs were not isolated. Confirm with staff.
- **TEMP-1:** the `2theta-temp.py` scan mode implies a sample temperature device (furnace / cryostream); its PV was not isolated in this pass, confirm (a possible TemperatureController consumer).
- PSS / hutch safety and passive beam-path tier not in the DAQ repo (SCOPE-1).
