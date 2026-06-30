# Fleet recurrence: Australian Synchrotron

Cross-fleet device-class frequency across the beamlines surveyed under `research/as/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

**Scope: 1 device-passed beamline (IMBL).** The MX3 beamline is modeled as a shipped deployment (built from `mx3-beamline-library`), not a Tier-2 `facts.md` pass; its device data lives in `deployments/mx3/beamline.yaml`. IMBL is the first AS Tier-2 device pass. A one-beamline research fleet produces no cross-beamline recurrence signal, so this is a curated single-beamline summary. Re-generate when a second AS beamline is device-passed.

## Family mapping (IMBL, curated)

IMBL (Imaging and Medical Beam Line) is a wiggler imaging / micro-CT / Microbeam-Radiation-Therapy beamline. The public source (`AustralianSynchrotron/imbl`, C++ Qt) covers the optics/shutter/safety front end; every device maps to an already-graduated catalog Family. See `beamlines/imbl/facts.md`.

| Catalog Family | IMBL devices | Status |
| --- | --- | --- |
| InsertionDevice | superconducting wiggler (SR08ID01:GAP_MONITOR) | graduated |
| Monochromator | bent-Laue DCM (SR08ID01DCM01:, Bragg/bender/tilt/X/Z axes) | graduated |
| Filter | filter paddles (SR08ID01FR01:) | graduated |
| Shutter | MRT fast shutter (SR08ID01MRT01:), front-end + 1A shutters | graduated |
| GenericProbe | EPS isolation/gate valves (loose) | graduated (loose) |
| SafetyStack | PSS personnel safety (SR08ID01PSS01:) | maps to CORA safety-BC seam, not a device |

## Graduation shortlist (the actionable output)

**Zero new families.** IMBL's front-end is pure reuse (InsertionDevice, Monochromator, Filter, Shutter). Two points worth recording:

- **MRT shutter -> Shutter vs TimingController (watch):** the Microbeam Radiation Therapy fast shutter (`SR08ID01MRT01:`) gates the beam in timed exposure cycles (CYCLEPERIOD / EXPOSUREPERIOD), so it straddles Shutter and TimingController. It is IMBL's distinctive device. Not a new family either way; flag the binding for confirmation. No other facility has an MRT shutter (medical therapy is unique to IMBL), so no rule-of-three.
- **Bent-Laue DCM:** a Monochromator variant (Laue geometry with four bender axes for the bent crystals), distinct from the flat-Bragg DCMs elsewhere but the same Monochromator family. The bender axes are components of the one Asset, not separate devices.

## Coverage note

The `imbl` repo is the optics/shutter/safety front end only. IMBL's imaging detectors (large-area flat panels, the CT detector) and the sample / CT-rotation / medical-imaging positioning stage are NOT in this repo (DET-1 / SAMPLE-1, staff questions). The `imblproc` / `imblScripts` repos cover CT *processing*, not device control. IMBL's multi-hutch topology (1A/2A/2B/3A/3B over ~140 m) is a staff question (HUTCH-1).

## Provenance

Mined by hand from the public `AustralianSynchrotron/imbl` C++ Qt control application (per-subsystem `pvBaseName` + literal axis suffix). All PV prefixes verified verbatim against the `*.cpp` sources (`SR08ID01DCM01:`, `SR08ID01FR01:`, `SR08ID01MRT01:`, `SR08ID01EPS01:IGV`, `SR08ID01PSS01:`, `SR08ID01:GAP_MONITOR`). Repo last pushed 2021; carry everything `confirm`. A different source idiom than the bluesky/ophyd/dodal/MXCuBE passes (C++ Qt over qtpv), the same honesty discipline applied.
