# Extracted facts: BMM (6-BM)

Candidate device facts for `bmm` (NSLS-II 6-BM, XAS / EXAFS). Candidates only; confirm every row before modeling. Source: the public `NSLS2/bmm-profile-collection` (`startup/BMM/*.py` ophyd device modules, read 2026-06). Every value is carried `confirm` until BMM staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "This is a worked example"
    BMM is already a shipped NSLS-II deployment, so this Tier-2 pass is a *reference*, not net-new modeling: it shows the practice end to end and is cross-checked against the shipped `deployments/bmm/beamline.yaml`. For a beamline that is not yet modeled, the facts.md is written the same way but feeds a fresh deployment scaffold (step 6).

## Device inventory

Map each device onto a CORA Family at **Asset granularity**: one row per stage / assembly, with the device-level PV prefix the descriptor binds. Component axes go in the Axes column (read verbatim from source), as the provenance that justifies the mapping. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| FrontEndShutter | Shutter | `XF:06BM-PPS{Sh:FE}` | (PPS shutter, no motor axes) | 6-BM-A | source | yes |
| PhotonShutter | Shutter | `XF:06BM-PPS{Sh:A}` | (PPS shutter) | 6-BM-A | source | yes |
| CollimatingMirror | Mirror | `XF:06BM-OP{Mir:M1` | yu=`-Ax:YU}Mtr`; ydo=`-Ax:YDO}Mtr`; ydi=`-Ax:YDI}Mtr`; xu=`-Ax:XU}Mtr`; xd=`-Ax:XD}Mtr` | 6-BM-A | source | yes |
| Monochromator | Monochromator | `XF:06BMA-OP{Mono:DCM1` | bragg=`-Ax:Bragg}Mtr`; para=`-Ax:Par2}Mtr`; perp=`-Ax:Per2}Mtr`; pitch=`-Ax:P2}Mtr`; roll=`-Ax:R2}Mtr`; x=`-Ax:X}Mtr`; y=`-Ax:Y}Mtr` | 6-BM-A | source | yes |
| FocusingMirror | Mirror | `XF:06BMA-OP{Mir:M2` | yu=`-Ax:YU}Mtr`; ydo=`-Ax:YDO}Mtr`; ydi=`-Ax:YDI}Mtr`; xu=`-Ax:XU}Mtr`; xd=`-Ax:XD}Mtr`; bend=`-Ax:Bend}Mtr` | 6-BM-A | source | yes |
| ConditioningSlit | Slit | `XF:06BMA-OP{Slt:01` | top/bottom/inboard/outboard blades | 6-BM-A | source | yes |
| SampleSlit | Slit | `XF:06BM-BI{Slt:02` | top/bottom/inboard/outboard blades | 6-BM-B | source | yes |
| Filter | Filter | `XF:06BMA-BI{Fltr:01` | y1=`-Ax:Y1}Mtr`; y2=`-Ax:Y2}Mtr` | 6-BM-A | source | yes |
| EnergyAxis | PseudoAxis | (pseudo; no PV) | DCM energy pseudo-positioner, limits 2900-25000 eV | 6-BM-A | source | yes |
| DiagnosticScreen | Screen | `XF:06BMA-BI{Diag:02` | y=`-Ax:Y}Mtr` | 6-BM-A | source | yes |
| BeamPositionMonitor | GenericProbe (?) | `XF:06BM-BI{BPM:1` | y=`-Ax:Y}Mtr` | 6-BM-A | source | yes |
| SampleStage | LinearStage | `XF:06BM-ES{MC:09` | x/y/z linked axes | 6-BM-B | sample | yes |
| SampleWheel | RotaryStage | `XF:06BMA-BI{XAFS-Ax:RotB}Mtr` | (single rotary axis) | 6-BM-B | sample | yes |
| ReferenceHolder | LinearStage | `XF:06BMA-BI{XAFS-Ax:RefX}Mtr` | (single linear axis) | 6-BM-B | sample | yes |
| IonChambers | FluxMonitor | `XF:06BM-BI{EM:1}EM180:` | I0/It/Ir/Iy derived currents (QuadEM) | 6-BM-B | detection | yes |
| FluorescenceSpectrometer | EnergyDispersiveSpectrometer | `XF:06BM-ES{Xsp:1}` | Xspress3; 1/4/7-element variants | 6-BM-B | detection | yes |
| ScalerCounter | GenericProbe (?) | `XF:06BM-ES:1{Sclr:1}` | (scaler channels) | 6-BM-B | detection | yes |
| EndstationMotionController | MotionController | `XF:06BM-ES{MC:09}` | (motion controller) | 6-BM-B | sample | yes |

The per-axis handles above are read verbatim from `dcm.py` / `motors.py` / `instruments.py` (DCM, M1, M2, filters); the pilot adversarial-verify confirmed every one against source. Slit blades and the scaler channels are real axes recorded at the Asset level here; expand them only if a deployment binds individual blades.

## Role hints

- **Positioner**: the DCM axes (bragg/para/perp/pitch/roll/x/y), both mirrors, both slits, the three sample stages (SampleStage, SampleWheel, ReferenceHolder). All are `EpicsMotor` subclasses in source (`FMBOEpicsMotor`, `VacuumEpicsMotor`, `XAFSEpicsMotor`, `BMMDeadBandMotor`).
- **Sensor**: IonChambers (the QuadEM `BMMQuadEM` exposes I0/It/Ir as derived currents, the flux signal), the BeamPositionMonitor, the ScalerCounter.
- **Detector**: FluorescenceSpectrometer (Xspress3, per-element MCA frames).
- **No Regulator / settable-continuous-setpoint actuator** is present in source. BMM's sample temperature (Linkam / Lakeshore) is not in the public profile collection; it is an open question, not modeled (see deferred/absent).

## Trust hints

`startup/user_group_permissions.yaml` (1.8 KB) is present: the queue-server group/permission model. CORA models its own Trust spine, so this is input to the seam read, not a binding. It confirms NSLS-II's queue-server is the orchestration layer CORA would replace (consistent with the facility survey section 3).

## New-family watch

Nothing new to coin. Every device maps to an existing catalog Family or a loose family already in use across the fleet:

- **IonChambers -> FluxMonitor** (graduated): a Sensor family earned by what it measures (flux). BMM is one of its consumers.
- **FluorescenceSpectrometer -> EnergyDispersiveSpectrometer** (graduated): the Xspress3, a Sensor family earned by what it measures (energy-dispersive fluorescence spectrum).
- **BeamPositionMonitor / ScalerCounter -> GenericProbe (loose)**: these stay loose. The beam-position concept is fragmented across `BeamPositionMonitor` / `Diagnostic` / `GenericProbe` strings fleet-wide and is held pending the `DIAG-1` cross-facility abstraction review; do not coin a Family from BMM alone.

## Deferred / absent

- **Sample environment (temperature).** BMM runs cryostats / furnaces (Linkam, Lakeshore) for in-situ XAS, but no temperature controller appears in the public profile collection. Open question `TEMP-1`; not modeled. If a Lakeshore/Eurotherm were instantiated here it would be a Regulator-presenting candidate (the TemperatureController lineage), but absence from source means it is a question, not a device.
- **The XRD / glancing-angle accessory** mentioned on the facility page is not in the startup device tree; deferred as `XRD-1`.
