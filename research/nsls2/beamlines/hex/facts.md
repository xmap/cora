# Extracted facts: HEX (27-ID)

Candidate device facts for `hex` (NSLS-II 27-ID, high-energy X-ray engineering / materials: energy-dispersive and monochromatic diffraction, tomography, imaging). Candidates only; confirm every row before modeling. Source: the public `NSLS2/hex-profile-collection` (`startup/*.py`, read 2026-06; modules `03-motors`, `05-providers`, `08-germ`, `09-panda`, `10-kinetix`, `11-perkin-elmer`, `13-smpl-align-cam`). Every value is carried `confirm` until HEX staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "Multi-modal high-energy engineering"
    HEX runs several techniques from one endstation: computed micro-tomography (CMT), monochromatic + energy-dispersive diffraction (DIFF / EDXD), and radiography/imaging (IMG), each with its own motion group under `XF:27IDF-OP:1{...}`. Detectors: GeRM (germanium strip, energy-dispersive), Perkin-Elmer (imaging), Kinetix (sCMOS). PandA + Kinetix drive fly-scans.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| FrontEndShutter | Shutter | `XF:27IDA-PPS{Sh:FE}` | (+ L1-S1 PPS) | 27-ID-A | source | yes |
| DoubleLaueMono | Monochromator | `XF:27IDA-OP:1{Mono:DCLM-Ax:` | double-Laue mono (high-energy) | 27-ID-A | optics | yes |
| Filter1 | Filter | `XF:27IDA-OP:1{Fltr:1-Ax:` | filter (+ Fltr:2/3/4 across OP:1/2/3) | 27-ID-A | optics | yes |
| WhiteBeamSlit | Slit | `XF:27IDA-OP:1{Slt:1-Ax:` | blade axes | 27-ID-A | optics | yes |
| EndstationSlit2 | Slit | `XF:27IDF-OP:1{Slt:2-Ax:` | blade axes | 27-ID-F | optics | yes |
| CMTSlit | Slit | `XF:27IDF-OP:1{Slt:CMT-Ax:` | tomography slit | 27-ID-F | optics | yes |
| CMTStage | LinearStage | `XF:27IDF-OP:1{CMT:1-Ax:` | computed-tomography sample motion | 27-ID-F | sample | yes |
| DiffractionStage | Diffractometer (?) | `XF:27IDF-OP:1{DIFF:1-Ax:` | diffraction motion group | 27-ID-F | sample | yes |
| EDXDStage | LinearStage | `XF:27IDF-OP:1{EDXD:1-Ax:` | energy-dispersive diffraction motion | 27-ID-F | sample | yes |
| ImagingStage | LinearStage | `XF:27IDF-OP:1{IMG:1-Ax:` | radiography/imaging motion | 27-ID-F | sample | yes |
| SampleStage | LinearStage | `XF:27IDF-OP:1{SMPL:1-Ax:` | sample positioning | 27-ID-F | sample | yes |
| OpticsStage1 | LinearStage | `XF:27IDF-OP:1{OPT:1-Ax:` | endstation optics (+ OPT:2) | 27-ID-F | optics | yes |
| Shield | Housing (?) | `XF:27IDF-OP:1{SHLD:1-Ax:` | motorized shield/enclosure | 27-ID-F | sample | yes |
| MotionController1 | MotionController | `XF:27IDF-OP:1{MC:1-Ax:` | motion controllers (MC:1, MC:5) | 27-ID-F | sample | yes |
| GeRMDetector | EnergyDispersiveSpectrometer | `XF:27ID1-ES{GeRM-Det:1}` | germanium strip detector (energy-dispersive) | 27-ID-1 | detection | yes |
| PerkinElmer | Camera | `XF:27ID1-ES{PE-Det:1}` | Perkin-Elmer flat-panel (imaging) | 27-ID-1 | detection | yes |
| SampleAlignCam | GenericProbe (?) | `XF:27ID1-ES{Sample-Cam:1}` | sample alignment camera | 27-ID-1 | sample | yes |

Device-level prefixes read verbatim from source: `Mono:DCLM`, the per-mode motion groups (`CMT:1`/`DIFF:1`/`EDXD:1`/`IMG:1`/`SMPL:1`), `GeRM-Det:1`, `PE-Det:1`. The Kinetix detector and PandA use composed `{kinetix_id}`/`{panda_id}` template prefixes (not isolated literals).

## Role hints

- **Positioner**: DCLM mono, filters, slits, and all the per-mode endstation motion groups (CMT/DIFF/EDXD/IMG/SMPL/OPT/SHLD), motion controllers.
- **Detector**: GeRM (energy-dispersive germanium), Perkin-Elmer (imaging), Kinetix (sCMOS, templated prefix).
- **Sensor**: sample alignment camera.
- **Timing**: PandA (fly-scan, templated prefix).

## Trust hints

`startup/user_group_permissions.yaml` present; queue-server orchestration. HEX uses `providers` (05-providers.py) for device construction. Aligns with `deployments/hex/`.

## New-family watch

No new coining. Notes:
- **DoubleLaueMono -> Monochromator** (graduated): same DLM pattern as XPD; bind directly.
- **GeRMDetector -> EnergyDispersiveSpectrometer** (graduated): a germanium strip energy-dispersive detector; bind directly (the WHAT-it-measures discriminator holds).
- **DiffractionStage -> Diffractometer (?)**: another loose Diffractometer candidate; same contested-contract question as chx/hxn/xpd. Adds to the recurrence watch; confirm contract.
- **Shield -> Housing (?)**: a motorized radiation shield; confirm Housing vs LinearStage.
- **Kinetix / PandA**: templated prefixes (`{kinetix_id}`/`{panda_id}`) resolved at runtime; their concrete PVs are confirm-pending, recorded but not bound to a literal.

## Deferred / absent

- **Kinetix** (`10-kinetix.py`) and **PandA** (`09-panda.py`) use runtime-templated PV prefixes not resolvable to literals from source; deferred `TEMPLATE-1` (confirm concrete PVs with staff).
- The high-energy **insertion-device source** referenced via providers; no standalone InsertionDevice instantiated; carry `SRC-1`.
