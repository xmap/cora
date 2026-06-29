# Extracted facts: 16bm-bits

Machine-extracted candidate facts for `16-BM` (facility `aps`). Candidates only; confirm every row before modeling. Source: the repo's Guarneri `devices.yml` plus ophyd device classes.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| scaler1 | GenericProbe | `16bmd:scaler1` | 16-BM-D | detection | scalers, detectors | yes |
| shutter | Shutter | - | ? | source | shutters | yes |

## Candidate enclosures

`16-BM-D` (all inferred, confirm).

## Role hints (from labels)

`Detector`

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
