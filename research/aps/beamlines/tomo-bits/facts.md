# Extracted facts: tomo-bits

Machine-extracted candidate facts for `tomo-bits` (facility `aps`). Candidates only; confirm every row before modeling. Source: the repo's Guarneri `devices.yml` plus ophyd device classes.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| optics | MCTOptics (?) | `2bm:MCTOptics:` | ? | source | optics | yes |
| shutter | Shutter | - | ? | source | shutters | yes |

## Candidate enclosures

None inferred from prefixes or labels.

## Role hints (from labels)

None.

## Trust hints (from user_group_permissions.yaml)

Candidate Trust Zones / Policies, one per queueserver user group:

- `root`: allowed plans `(none)`; allowed devices `(none)`
- `primary`: allowed plans `:.*`; allowed devices `:?.*:depth=5`
- `test_user`: allowed plans `:^count, :scan$`; allowed devices `:^det:?.*, :^motor:?.*, :^sim_bundle_A:?.*`

## Simulated devices (excluded from the candidate)

`sim_motor`, `sim_det`

## Open confirms

- **optics** (`tomo_instrument.devices.mct_optics.MCTOptics`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'MCTOptics'; needs a CORA Family
    - enclosure unresolved from prefix or labels
- **shutter** (`apstools.devices.SimulatedApsPssShutterWithStatus`)
    - no prefix and no resolvable axes
    - enclosure unresolved from prefix or labels
    - ophyd class 'SimulatedApsPssShutterWithStatus' not found in devices/*.py
