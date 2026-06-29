# Extracted facts: 11bm-bits

Machine-extracted candidate facts for `11-BM` (facility `aps`). Candidates only; confirm every row before modeling. Source: the repo's Guarneri `devices.yml` plus ophyd device classes.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| scaler1 | GenericProbe | `11bmb:scaler1` | 11-BM-B | detection | scalers, detectors | yes |
| shutter | Shutter | - | ? | source | shutters, baseline | yes |
| slew | SlewDevice (?) | `11bmb:` | 11-BM-B | source | slew | yes |
| spinner | EpicsSignal (?) | - | ? | source | - | yes |
| spy_lambda | SpyLambda (?) | `11bmbLambda:` | 11-BM-B | source | - | yes |
| tth | EpicsMotor (?) | `11bmb:m28` | 11-BM-B | source | motor | yes |

## Candidate enclosures

`11-BM-B` (all inferred, confirm).

## Role hints (from labels)

`Detector`, `Positioner`

## Trust hints (from user_group_permissions.yaml)

Candidate Trust Zones / Policies, one per queueserver user group:

- `root`: allowed plans `(none)`; allowed devices `(none)`
- `primary`: allowed plans `:.*`; allowed devices `:?.*:depth=5`
- `test_user`: allowed plans `:^count, :scan$`; allowed devices `:^det:?.*, :^motor:?.*, :^sim_bundle_A:?.*`

## Simulated devices (excluded from the candidate)

`sim_motor`, `sim_det`

## Open confirms

- **scaler1** (`ophyd.scaler.ScalerCH`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - ophyd class 'ScalerCH' not found in devices/*.py
- **shutter** (`apstools.devices.SimulatedApsPssShutterWithStatus`)
    - no prefix and no resolvable axes
    - enclosure unresolved from prefix or labels
    - ophyd class 'SimulatedApsPssShutterWithStatus' not found in devices/*.py
- **slew** (`bm11_b.devices.slew_scan_devices.SlewDevice`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'SlewDevice'; needs a CORA Family
    - mda_root: non-literal or absent component suffix
- **spinner** (`ophyd.EpicsSignal`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignal'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignal' not found in devices/*.py
- **spy_lambda** (`bm11_b.devices.slew_scan_devices.SpyLambda`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'SpyLambda'; needs a CORA Family
- **tth** (`ophyd.EpicsMotor`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'EpicsMotor'; needs a CORA Family
    - ophyd class 'EpicsMotor' not found in devices/*.py
