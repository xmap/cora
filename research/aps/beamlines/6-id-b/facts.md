# Extracted facts: 6-ID-B

Machine-extracted candidate facts for `6-ID-B` (facility `aps`), then curated. Candidates only; confirm every row before modeling. Source: the repo's Guarneri `devices.yml` plus ophyd device classes.

Curation note: `BCDA-APS/6idb-bits` is a fork of `BCDA-APS/polar-bits` (4-ID) with a grafted 6-ID-B endstation. 6-ID-B is physically Sector 6, a separate beamline from 4-ID. The 4-ID devices in the fork are identical to `polar-bits` and live in [`../4-id/`](../4-id/facts.md); this file keeps only the 6-ID-B-station devices so the two physical beamlines do not double-count in `recurrence.md`. The carve is by enclosure: every row below is enclosure `6-ID-B`.

## Device inventory

| Device | Suggested family | PV / axes | Enclosure | Stage | Labels | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| crl | mb_creator (?) | `6idbSoft:TRANS:` | 6-ID-B | source | - | yes |
| psic | creator (?) | `6idb1:` | 6-ID-B | source | diffractometer, hklpy2 | yes |
| psic_psi | creator (?) | `6idb1:` | 6-ID-B | source | diffractometer, hklpy2 | yes |
| psic_q | creator (?) | `6idb1:` | 6-ID-B | source | diffractometer, hklpy2 | yes |

## Candidate enclosures

`6-ID-B` (inferred, confirm).

## Role hints (from labels)

`Positioner`

## Open confirms

- **crl** (`apstools.devices.mb_creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'mb_creator'; needs a CORA Family
    - factory device (ad_creator): plugins and file paths need a human
    - ophyd class 'mb_creator' not found in devices/*.py
- **psic** (`hklpy2.creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'creator'; needs a CORA Family
    - ophyd class 'creator' not found in devices/*.py
- **psic_psi** (`hklpy2.creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'creator'; needs a CORA Family
    - ophyd class 'creator' not found in devices/*.py
- **psic_q** (`hklpy2.creator`)
    - axes unresolved: pv is the device prefix, per-axis PVs need confirm
    - family is the ophyd class name 'creator'; needs a CORA Family
    - ophyd class 'creator' not found in devices/*.py
