# Extracted facts: OPLS (12-ID-1)

Candidate device facts for `opls` (NSLS-II 12-ID-1, soft-matter / SAXS branch sharing the 12-ID straight with SMI at 12-ID-2). Candidates only; confirm every row before modeling. Source: the public `NSLS2/opls-profile-collection` (`startup/*.py`, read 2026-06; modules `08-shutter`, `09-machine`, `11-energy`, `12-xbpm`, `13-bimorph`, `14-crl`, `20-motors`, + SAXS/sample modules). Every value is carried `confirm` until OPLS staff verify it: the profile collection is strong evidence, not a CORA-owned fact.

!!! note "Distinct from SMI; shares the 12-ID sector"
    OPLS is its OWN beamline (tiled namespace `["opls"]`, name="opls") at 12-ID-1, NOT a duplicate of SMI (12-ID-2). The two share the 12-ID straight and some upstream optics (`XF:12ID-*`, `XF:12ID:m65-68`), but OPLS has its own SAXS endstation, CRL, and sample stage. COVERAGE-1: the public OPLS profile is THIN; a standalone mono is not in the read modules (likely shared 12-ID optics), so the optics chain is partly deferred, not invented.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, component axes as sub-detail read verbatim from source. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | Axes (component handles) | Enclosure | Stage | Confirm |
| --- | --- | --- | --- | --- | --- | --- |
| PhotonShutter | Shutter | `XF:12IDA-PPS:2{PSh}` | (PPS shutter, 12-ID branch 2) | 12-ID-A | source | yes |
| Transfocator | Transfocator | `XF:12ID1-OP{CRL-Ax:` | CRL lens-stack axes | 12-ID-1 | optics | yes |
| SharedOpticsMotors | LinearStage (?) | `XF:12ID:m65` | shared 12-ID motors (m65-m68) | 12-ID | optics | yes |
| SampleStage | LinearStage | `XF:12ID1-ES{Smpl-Ax:` | sample positioning | 12-ID-1 | sample | yes |
| CrystalDeflector | Mirror (?) | `XF:12ID1-ES{XtalDfl-Ax:` | crystal deflector axes | 12-ID-1 | optics | yes |
| Chiller | TemperatureController (?) | `XF:12ID1-ES{Chiller}` | sample/detector chiller | 12-ID-1 | sample | yes |
| SAXSStage | LinearStage | `XF:12ID1-ES{SAXS-Ax:` | SAXS flight-path / stage | 12-ID-1 | detection | yes |
| SAXSDetectorStage | LinearStage | `XF:12ID1-ES{DetSAXS-Ax:` | SAXS detector positioning | 12-ID-1 | detection | yes |
| BeamPositionMonitor | GenericProbe (?) | `XF:12IDA-BI:2{EM:BPM1}` | EM BPMs (BPM1/2 at 12-IDA, BPM3 at 12-IDB) | 12-ID-A | diagnostics | yes |

Device-level prefixes read verbatim from source: `XF:12IDA-PPS:2{PSh}`, `CRL-Ax:`, the `SAXS`/`DetSAXS`/`Smpl`/`XtalDfl` endstation stages, `Chiller`, the `EM:BPM1-3` electrometer BPMs, the shared `XF:12ID:m65-68` motors.

## Role hints

- **Positioner**: CRL, sample stage, crystal deflector, SAXS + detector stages, shared optics motors.
- **Sensor**: EM BPMs.
- **Regulator (?)**: the Chiller, if it presents a settable temperature setpoint.
- **Detector**: the SAXS area detector sits on `DetSAXS` (the detector device itself is on the SAXS stage; confirm the camera PV with staff).

## Trust hints

`startup/00-startup.py` configures its own tiled namespace `["opls"]["raw"]` and `name="opls"` (the `TILED_BLUESKY_WRITING_API_KEY_OPLS` env var), confirming OPLS is a distinct beamline data-stream from SMI. Queue-server orchestration applies.

## New-family watch

No new coining. Notes:
- **Transfocator** (graduated): OPLS is another CRL consumer; bind directly. (With chx/hxn/smi this further reinforces.)
- **CrystalDeflector -> Mirror (?)**: a crystal deflector steers the beam; confirm Mirror vs a dedicated deflector family (single use, do not coin).
- **Chiller -> TemperatureController (?)**: confirm it presents Regulator (settable setpoint) vs a read-only utility; if settable, another Regulator consumer.
- **BPM -> GenericProbe (loose)**: held DIAG-1.

## Deferred / absent

- **COVERAGE-1**: the public OPLS profile is thin. A standalone monochromator, mirrors, and white-beam slits are NOT in the read modules; OPLS shares the 12-ID upstream optics with SMI (`XF:12ID-*`, `XF:12ID:m65-68`). The shared optics chain is deferred, not invented; cross-check with SMI's 12-ID optics and confirm the sharing with staff.
- The **SAXS area detector** camera PV (vs the `DetSAXS` stage) is deferred `DET-1`.
- The **insertion-device source** at 12-ID is shared; `SRC-1`.
