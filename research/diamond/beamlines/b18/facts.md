# Extracted facts: B18

Candidate device facts for `b18` (Diamond Light Source B18, core X-ray absorption spectroscopy: XAS / EXAFS). Candidates only; confirm every row before modeling. Source: the public `DiamondLightSource/dodal` (`src/dodal/beamlines/b18.py`, read 2026-06). Every value is carried `confirm` until B18 staff verify it: dodal is strong evidence, not a CORA-owned fact.

!!! warning "Stub module: no devices in public dodal"
    The public b18 dodal module is a STUB: it instantiates only the shared `Synchrotron` machine-status device and carries NO beamline devices, no PVs. B18's instruments, the scanning DCM (the XAS energy-scan engine), ion chambers, fluorescence detector, and sample environment, are ABSENT from public dodal. Per the partial-scaffold discipline, the whole device set is open questions, NOT invented. dodal prefix root would be **BL18B** (env-resolved) once devices land.

## Device inventory

Asset granularity. The public module exposes no beamline devices.

| Device | Suggested family | PV prefix | dodal class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| Synchrotron | GenericProbe (?) | (shared machine status, no beamline PV) | Synchrotron | source | yes |

No beamline device PVs are present in the public module; the single factory is the shared `Synchrotron()` status device (no constructor prefix).

## Role hints

- None beyond the shared synchrotron status device.

## Trust hints

dodal controls library; B18 runs bluesky/GDA over devices not exposed in the public module. Trust modeled CORA-native.

## New-family watch

Nothing to assess: no beamline devices in source. No coining, no reuse signal.

## Deferred / absent (the whole beamline)

B18's entire device set is absent from public dodal, all open questions:
- **MONO-1**: the scanning **DCM** (the XAS / EXAFS energy-scan monochromator). This is the device the pending `energy_scan` Capability graduation wants instantiated in dodal; B18 does NOT provide it (the survey's "B18 is thin" confirmed: it is a stub). The scanning-XAS energy_scan earn remains unsatisfiable from current dodal.
- **DET-1**: ion chambers (transmission XAS) + fluorescence detector (Xspress3-class).
- **OPTICS-1**: mirrors, slits, attenuators, harmonic-rejection.
- **ENV-1**: sample environment (furnaces, cryostats, the in-situ catalysis rigs B18 is known for).
- PSS / hutch safety and passive beam-path tier not in dodal (SCOPE-1).

This is a faithful stub: B18 is not meaningfully modellable from public dodal today. The deployment, if built, would need staff-provided device facts (or a future dodal module). Recorded here so the facility recurrence and coverage are honest about B18's status.
