# Controls

*The control stack, its config-driven instrument map, and the bluesky-orchestration seam. First cut; handles read from the profile, carried confirm.*

SST runs on the NSLS-II EPICS / ophyd control stack, the same floor as the other NSLS-II beamlines. CORA observes that floor and, where it replaces bluesky-style orchestration, conducts over it; it does not replace EPICS itself.

## Device handles (config-driven)

SST is the config-driven extraction mode: device instances are declared in the beamline's bluesky profile collections ([NSLS2/sst-rsoxs-profile-collection](https://github.com/NSLS2/sst-rsoxs-profile-collection), [NSLS2/sst-haxpes-profile-collection](https://github.com/NSLS2/sst-haxpes-profile-collection)) as `devices.toml` blocks (a `prefix` + a `_target` class), and the per-axis PV grammar lives in the shared [NSLS-II-SST/sst-base](https://github.com/NSLS-II-SST/sst-base) library. The descriptor's handles combine the toml prefix with the class suffixes, so they are verified against both sources. They remain confirm-pending (`CTRL-1`).

Two config-driven subtleties carried into the descriptor: the soft PGM's instance prefix is empty in the toml (a factory call), so its real base `XF:07ID1-OP{Mono:PGM1` is read from the `sst-base` library; and the tender DCM hardcodes `XF:07ID6-OP{Mono:DCM1` rather than inheriting the undulator prefix. Both are confirmed against the library source.

## The orchestration seam

The soft-energy and tender-energy moves, the RSoXS scans, and the HAXPES analyzer sweeps run through bluesky plans and the queue server. That orchestration is the seam CORA's edge replaces: CORA conducts the run over the `ControlPort`, driving through ophyd / EPICS rather than replacing it. The detector file-writing to the NSLS-II filestore is plumbing CORA observes, not data it owns; CORA keeps its own data-of-record.

## Equipment protection

SST carries an equipment-protection interlock separate from the personnel PSS, as the other NSLS-II beamlines do, with the UHV endstations adding vacuum interlocks (gate valves, pressure trips). CORA does not model the interlock logic; it would only observe outcomes, mapping vacuum and utility faults to Supply status and device faults to an Asset condition. That mapping is not modelled in this cut.
