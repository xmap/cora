# Extracted facts: CDI (9-ID)

Candidate device facts for `cdi` (NSLS-II 9-ID, coherent diffractive imaging: forward CDI, ptychography, Bragg CDI). Candidates only; confirm every row before modeling. Source: the public `NSLS2/cdi-profile-collection` (`startup/*.py`, read 2026-06; modules `10-machine`, `18-screens`, `20-motors`, `30-area-detectors`, `31-electrometers`). Every value is carried `confirm` until CDI staff verify it.

!!! note "Coherent imaging with a KB nanofocus"
    CDI uses a KB-mirror nanofocus, Eiger + Merlin photon-counting detectors, and i400/i404 electrometers, with fluorescent screens along the photon-management mirror train (VPM/HPM/DM).

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| KBMirrorHorizontal | Mirror | `XF:09IDC-OP:1{Mir:KBh-Ax:` | KB horizontal refocus | 9-ID-C | source | yes |
| KBMirrorVertical | Mirror | `XF:09IDC-OP:1{Mir:KBv-Ax:` | KB vertical refocus | 9-ID-C | source | yes |
| PhotonMirrorScreens | Screen | `XF:09IDA-OP:1{FS:VPM-Ax:` | fluorescent screens on VPM/HPM/DM2 mirror train | 9-ID-A | source | yes |
| Eiger1 | Camera | `XF:09ID1-ES{Det:Eig1}` | Eiger photon-counting detector | 9-ID-1 | detection | yes |
| Merlin1 | Camera | `XF:09ID1-ES{Det:Merlin1}` | Merlin photon-counting detector | 9-ID-1 | detection | yes |
| Electrometer400 | FluxMonitor (?) | `XF:09IDA-BI{i400:1}` | i400 electrometer (optics I0) | 9-ID-A | detection | yes |
| Electrometer404 | FluxMonitor (?) | `XF:09IDB-BI{i404:1}` | i404 electrometer (endstation) | 9-ID-B | detection | yes |
| BeamPositionMonitor1 | GenericProbe (?) | `XF:09IDC-BI{BPM:1}` | beam position monitor | 9-ID-C | source | yes |
| KBScreens | Screen | `XF:09IDC-BI{FS:KBh-Cam:8}` | KB-mirror fluorescent screens (KBh/KBv) | 9-ID-C | source | yes |
| SampleViewCamera | GenericProbe (?) | `XF:09IDC-BI{SMPL-Cam:10}` | sample viewing camera | 9-ID-C | sample | yes |

Device-level prefixes read verbatim from source: `Mir:KBh/KBv`, the `FS:VPM/HPM/DM2/KBh/KBv` screens, `Det:Eig1`/`Det:Merlin1`, `i400:1`/`i404:1` electrometers.

## Role hints

- **Positioner**: KB mirrors, fluorescent screen stages.
- **Sensor**: i400/i404 electrometers (I0/flux), BPM, sample camera.
- **Detector**: Eiger, Merlin (coherent imaging).

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration. CDI is a shipped deployment; aligns with `deployments/cdi/`.

## New-family watch

No new coining. Confirmations:
- **KB mirrors -> Mirror**, **Eiger/Merlin -> Camera**, **screens -> Screen (loose)**: bind directly.
- **i400/i404 -> FluxMonitor (?)**: I0 electrometers; intensity side FluxMonitor, confirm.
- **BPM / sample camera -> GenericProbe (loose)**: held DIAG-1.

## Deferred / absent

- **Mono, the coarse sample/ptychography scanning stack**: the public modules emphasize KB optics + photon management + detectors; the sample fine-scanning (ptychography piezo) is not isolated to literals here (`SCAN-1`).
- The **insertion-device source** referenced via `10-machine.py`; no standalone InsertionDevice instantiated; carry `SRC-1`.
