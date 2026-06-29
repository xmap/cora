# Extracted facts: 12id-bits

Machine-extracted candidate facts for `12-ID` (facility `aps`). Candidates only; confirm every row before modeling. Source: the repo's Guarneri `devices.yml` plus ophyd device classes.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| pilatus2m | Camera | `S12-PILATUS1:` | ? | detection | area_detector, detectors, SAXS | yes |
| pilatus900k | Camera | `12idcPIL:` | 12-ID-C | detection | area_detector, detectors, WAXS | yes |
| xsp3 | Camera | - | ? | detection | - | yes |
| sample_stage | mb_creator (?) | `12idc:` | 12-ID-C | sample | sample | yes |
| beamstop | mb_creator (?) | `12ideSFT:` | 12-ID-E | source | beamstop | yes |
| saxs_det_stage | mb_creator (?) | `12idcACS1:` | 12-ID-C | source | detector_stage, baseline, SAXS | yes |

## Candidate enclosures

`12-ID-C`, `12-ID-E` (all inferred, confirm).

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

- **beamstop** (`apstools.devices.motor_factory.mb_creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'mb_creator'; needs a CORA Family
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'mb_creator' not found in devices/*.py
- **pilatus2m** (`apstools.devices.area_detector_factory.ad_creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - enclosure unresolved from prefix or labels
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'ad_creator' not found in devices/*.py
- **pilatus900k** (`apstools.devices.area_detector_factory.ad_creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'ad_creator' not found in devices/*.py
- **sample_stage** (`apstools.devices.motor_factory.mb_creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'mb_creator'; needs a CORA Family
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'mb_creator' not found in devices/*.py
- **saxs_det_stage** (`apstools.devices.motor_factory.mb_creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'mb_creator'; needs a CORA Family
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'mb_creator' not found in devices/*.py
- **xsp3** (`apstools.devices.area_detector_factory.ad_creator`)
    - no prefix and no resolvable axes
    - enclosure unresolved from prefix or labels
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'ad_creator' not found in devices/*.py
