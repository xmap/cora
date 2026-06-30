# Extracted facts: CSX (23-ID-1)

Candidate device facts for `csx` (NSLS-II 23-ID-1, coherent soft X-ray scattering and resonant soft X-ray scattering, RSXS, on the TARDIS diffractometer). Candidates only; confirm every row before modeling. Source: the public `NSLS2/csx-profile-collection` (`startup/02-nanops.py`, read 2026-06). The public profile collection is THIN: only the nanopositioner + diffractometer device group is present at the top level. Every value is carried `confirm` until CSX staff verify it.

!!! note "Thin public source; twin of IOS on the canted 23-ID straight"
    CSX shares the 23-ID straight with IOS (IOS is 23-ID-2, CSX is 23-ID-1). The public profile collection exposes only the sample nanopositioner + a diffractometer angle group; the EPU source, grating mono, and detectors are not in the read module. CSX is a shipped deployment that graduated the GratingMonochromator family; this Tier-2 pass records only what public source supports.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| Diffractometer | Diffractometer (?) | `XF:23ID1-ES{Dif:Nano-Ax:` | TARDIS nano-diffractometer angle axes | 23-ID-1 | sample | yes |
| NanoPositioner | LinearStage | `XF:23ID1-ES{PA-Ax:` | piezo nanopositioner (sample) | 23-ID-1 | sample | yes |

Device-level prefixes read verbatim from source: `Dif:Nano` (TARDIS), `PA` (piezo nanopositioner). Only these two device groups appear in the public `02-nanops.py`.

## Role hints

- **Positioner**: TARDIS diffractometer angles, piezo nanopositioner.

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration. CSX is a shipped deployment (it graduated GratingMonochromator). Aligns with `deployments/csx/`; the deployment models more than this thin public module exposes.

## New-family watch

- **Diffractometer (?)**: `Dif:Nano` (TARDIS) is another loose Diffractometer consumer. The TARDIS is a genuine multi-circle soft X-ray diffractometer, a stronger Diffractometer-family signal than the detector-arm stubs elsewhere; weigh it when resolving the Diffractometer graduation contract.
- **GratingMonochromator** (graduated via CSX): not in this thin module, but CSX is the family's origin; the deployment binds it.

## Deferred / absent

- **EPU source, grating mono, detectors, electrometers**: ABSENT from the public `02-nanops.py` (the only device module). Not invented; the shipped `deployments/csx/` carries them from a fuller read or staff input. Public-source device coverage here is intentionally minimal (`COVERAGE-1`).
