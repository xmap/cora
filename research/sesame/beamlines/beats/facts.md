# Extracted facts: BEATS (ID10)

Candidate device facts for `beats` (SESAME BEATS, BEAmline for Tomography at SESAME: full-field X-ray micro-CT). Candidates only; confirm every row before modeling. Source: the public `SESAME-Synchrotron/BEATS_tomoscan` repo (read 2026-06), the EPICS IOC `tomoScan.substitutions` (the most authoritative SESAME device source: literal PV macros). Every value is carried `confirm` until BEATS staff verify it: the facility IOC config is strong evidence, not a CORA-owned fact.

!!! note "Richest SESAME source: literal IOC substitutions"
    BEATS publishes the actual EPICS IOC substitutions for its tomoscan, with every device macro expanded to a literal PV (rotation, sample X/Y, cameras, combined stopper/shutter, pressure interlocks, valves). PV roots use the SESAME `I10` (beamline ID10) scheme: `I10R3-MO-ACS:...` (rack 3 motion / ACS controller), `I10R2-MO-MC2:...` (rack 2 / MC2 controller), `I10OH-VA-...` (optics-hutch vacuum), `I10EH-ES-...` (endstation). The tomoscan `P` prefix is `tomoscanBEATS:`. Variants exist for FLIR + PCO cameras, continuous + step scan.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV (verbatim from source), role as sub-detail. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV (verbatim) | role | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| RotationStage | RotaryStage | `I10R3-MO-ACS:EH-TMO-SRV-ROT:m1` | ACS servo rotation (continuous tomography) | sample | yes |
| SampleStageX | LinearStage | `I10R2-MO-MC2:EH-TMO-STP-TRSX1` | MC2 stepper translation X | sample | yes |
| SampleStageY | LinearStage | `I10R2-MO-MC2:EH-TMO-STP-TRSY1` | MC2 stepper translation Y | sample | yes |
| FLIRCamera | Camera | `FLIR:` (+ `FLIR:HDF1:`) | FLIR detector + HDF writer | detection | yes |
| PCOCamera | Camera | `PCO:` (+ `PCO:HDF1:`) | PCO detector + HDF writer | detection | yes |
| CombinedStopperShutter | Shutter | `I10OH-VA-COMB:setClose` / `setOpen` / `getStatus` | optics-hutch combined stopper+shutter | source | yes |
| RotationMaxSpeed | GenericProbe (?) | `BEATS:RotInt:MaxSpeed.VAL` | rotation speed limit setting | sample | yes |
| PressureInterlocks | GenericProbe (?) | `I10EH-ES-ACS-PRESSURE-R:isOn`, `-CLAMPX:isOn`, `-PRESSURE-Y:isOn` | air-bearing pressure interlocks | sample | yes |
| MotorEnables | GenericProbe (?) | `I10EH-ES-ACS-R-MOTOR:isEnabled`, `-X-MOTOR`, `-Y-MOTOR` | motor enable status | sample | yes |
| PneumaticValves | GenericProbe (?) | `I10EH-ES-ACS-VALVE-X:turnOn`, `-VALVE-Y:turnOff` | air-bearing valves | sample | yes |
| EmergencyStop | GenericProbe (?) | `I10EH-ES-ACS-EM:isPressed`, `I10EH-ES-ACS:reset` | emergency button / reset | sample | yes |
| BeamReadyPermit | GenericProbe (?) | `BEAMREADY:ShutterPermit` | beam-ready shutter permit | source | yes |

Device-level handles read verbatim from the IOC substitutions: `I10R3-MO-ACS:EH-TMO-SRV-ROT:m1` (rotation), `I10R2-MO-MC2:EH-TMO-STP-TRSX1`/`TRSY1` (sample X/Y), `FLIR:HDF1:` / `PCO:HDF1:` (cameras), `I10OH-VA-COMB:setClose/setOpen/getStatus` (combined stopper/shutter), the ACS pressure-interlock / valve / enable / emergency PVs, `BEATS:RotInt:MaxSpeed.VAL`.

## Role hints

- **Positioner**: the ACS servo rotation stage (the tomography axis), the MC2 sample X/Y translations.
- **Detector**: FLIR + PCO cameras (full-field projection imaging), each with an HDF writer.
- **Shutter**: the combined stopper+shutter (`COMB`).
- **Sensor / interlock**: the air-bearing pressure interlocks, motor enables, valves, emergency button, beam-ready permit (the ACS air-bearing rotation safety chain).
- **Fly-scan**: the continuous variant rotates the ACS servo while triggering the camera, the fly tomography acquisition; the step variant is the alternative.

## Trust hints

Facility-org EPICS IOC + tomoscan (the APS `tomoscan` lineage, customized for BEATS); `BEATS_Dashboard` is the EPICS-Qt operator GUI. No queue-server; the tomoscan IOC + scan plans are the orchestration CORA's EdgeConductor would conduct over. This is the same `tomoscan` family CORA's 2-BM / FXI / TomoWise tomography deployments relate to.

## New-family watch

No new coining, pure tomography reuse:
- **RotationStage -> RotaryStage** (graduated): the ACS servo tomography rotation; bind directly. (An air-bearing servo, but the family is RotaryStage; the air-bearing interlocks are the GenericProbe safety cluster.)
- **SampleStageX/Y -> LinearStage** (graduated).
- **FLIR / PCO -> Camera** (graduated): two full-field tomography cameras.
- **CombinedStopperShutter -> Shutter** (graduated): the COMB combined stopper+shutter; one device that is both, confirm the modeling (a Shutter that also stops).
- **Pressure interlocks / valves / enables / emergency / beam-ready -> GenericProbe (loose)**: the air-bearing rotation safety + utility cluster (DIAG-1-like); held.

## Deferred / absent

- **OPTICS-1:** the white/pink-beam tomography optics (filters, the source, any mono for monochromatic CT) are not in the tomoscan IOC (it is sample + rotation + camera focused); confirm with staff (BEATS is a bending-magnet / wiggler white-beam CT beamline).
- The `BEATS_recon` repo (tomopy/dxchange reconstruction) is compute, not devices; modeled as a JobRunner port roundtrip at deployment time, not an Asset.
- PSS / hutch safety beyond the ACS interlocks not in the DAQ repo (SCOPE-1).
