# Fleet recurrence: ALBA

Cross-fleet device-class frequency across the beamlines surveyed under `research/alba/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

**Scope: 1 device-passed beamline (XALOC / BL13, MX).** ALBA's per-beamline device topology is otherwise firewalled (Sardana/Taurus config on `*.cells.es`); the single exception is XALOC, whose MX topology is public via its MXCuBE hardware-object config. A one-beamline fleet produces no cross-beamline recurrence signal, so this report is a curated single-beamline summary, not a frequency table. Re-generate when a second ALBA beamline is device-passed (the sibling MX beamline BL06 XAIRA, if it publishes a similar MXCuBE config, is the natural next).

## Family mapping (XALOC, curated)

XALOC is a kappa-geometry MX beamline. Every device maps to an already-graduated catalog Family; the MXCuBE service objects are orchestration/LIMS seam, not Assets. See `beamlines/xaloc/facts.md` for the full per-device mapping.

| Catalog Family | XALOC devices | Status |
| --- | --- | --- |
| Goniometer | mini-diff kappa goniometer (omega/kappa/kappaphi/centx/centy/omegax/y/z) | graduated (i03) |
| Monochromator | energy / wavelength | graduated |
| Camera | Pilatus + on-axis-view Lima video | graduated |
| LinearStage | detector-distance, zoom, sample-view stages | graduated |
| Shutter | fast / slow / photon shutters + front end | graduated |
| Filter | transmission / calibration attenuation | graduated |
| FluxMonitor | flux / beam-info | graduated |
| BeamStop | bstopz | graduated |
| Positioner | CATS sample-changer robot (+ Clearance + Subject custody) | graduated (role-as-family; robot folds here) |
| GenericProbe | mach-info ring status | graduated (loose) |

## Graduation shortlist (the actionable output)

**Zero new families.** XALOC is pure reuse of the MX vocabulary already graduated at i03 / the NSLS-II MX fleet (Goniometer, Monochromator, Camera, Shutter, Filter, FluxMonitor, BeamStop) plus the robot-as-Positioner pattern. No signal toward any new Family from a single MX beamline.

Notable for the cross-facility picture: the **CATS sample-changer robot** here is the same robot family seen at SESAME, the NSLS-II/Diamond MX beamlines, and SOLEIL; it consistently folds to Positioner + Clearance + Subject custody rather than a SampleChanger Family, reinforcing that decision across yet another facility.

## Provenance

Extracted by `scripts/reverse_engineer --source mxcube` from the public `mxcube/mxcubecore` `configuration/alba_xaloc13` hardware-object config (42 devices, 6 bookkeeping rows filtered), then human-curated (family mapping in `facts.md`). Real Tango handles verified (`bl13/eh/pilatuslima`, `bl13/eh/cats`, Taurus motor names). The raw machine-frequency table the extractor emits for a single beamline is not meaningful (every class appears once); this curated summary supersedes it.
