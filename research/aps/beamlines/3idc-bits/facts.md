# Extracted facts: 3idc-bits

Machine-extracted candidate facts for `3-ID` (facility `aps`). Candidates only; confirm every row before modeling. Source: the repo's Guarneri `devices.yml` plus ophyd device classes.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| eiger2 | Camera | `dp_eiger_sn:` | ? | detection | area_detector, detectors | yes |
| scaler_b | GenericProbe | `3ida:scaler1` | 3-ID-A | detection | scalers, detectors | yes |
| scaler_c | GenericProbe | `3ids:scaler1` | 3-ID-S | detection | scalers, detectors | yes |
| IC0_B_VDC | EpicsSignalRO (?) | - | ? | source | monitor | yes |
| IC0_C_VDC | EpicsSignalRO (?) | - | ? | source | monitor | yes |
| detector_stage | mb_creator (?) | - | ? | source | baseline | yes |
| laser_optics | LaserOptics (?) | `3idxps1:` | 3-ID-X | source | baseline | yes |
| sample_stage | mb_creator (?) | - | ? | source | baseline | yes |
| shutterc | Shutter | `3ida:shutterC:` | 3-ID-A | source | shutters, baseline | yes |

## Candidate enclosures

`3-ID-A`, `3-ID-S`, `3-ID-X` (all inferred, confirm).

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

- **IC0_B_VDC** (`ophyd.EpicsSignalRO`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignalRO'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignalRO' not found in devices/*.py
- **IC0_C_VDC** (`ophyd.EpicsSignalRO`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'EpicsSignalRO'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - ophyd class 'EpicsSignalRO' not found in devices/*.py
- **detector_stage** (`apstools.devices.motor_factory.mb_creator`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'mb_creator'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'mb_creator' not found in devices/*.py
- **eiger2** (`apstools.devices.ad_creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - enclosure unresolved from prefix or labels
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'ad_creator' not found in devices/*.py
- **laser_optics** (`id3c.devices.laser_optics.LaserOptics`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'LaserOptics'; needs a CORA Family
    - in_position: non-literal or absent component suffix
    - out_position: non-literal or absent component suffix
    - tolerance: non-literal or absent component suffix
    - settle_time: non-literal or absent component suffix
    - out_status: non-literal or absent component suffix
- **sample_stage** (`apstools.devices.motor_factory.mb_creator`)
    - no prefix and no resolvable axes
    - family is the ophyd class name 'mb_creator'; needs a CORA Family
    - enclosure unresolved from prefix or labels
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'mb_creator' not found in devices/*.py
- **scaler_b** (`ophyd.scaler.ScalerCH`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - ophyd class 'ScalerCH' not found in devices/*.py
- **scaler_c** (`ophyd.scaler.ScalerCH`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - ophyd class 'ScalerCH' not found in devices/*.py
- **shutterc** (`apstools.devices.ApsPssShutter`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - ophyd class 'ApsPssShutter' not found in devices/*.py
