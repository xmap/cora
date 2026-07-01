# Fleet recurrence: Sirius (LNLS)

Cross-fleet device-class frequency across the beamlines surveyed under `research/sirius/beamlines/`. The point of this report is the **catalog Family graduation signal**: a device class that recurs across two or more *physically distinct* beamlines is a graduation candidate (rule-of-three is the firm trigger; two is a watch). `graduated` marks classes already in `catalog/catalog.yaml`.

**Scope: 1 device-passed beamline (Manaca, MX).** Sirius's per-beamline device topology is otherwise firewalled (`gitlab.cnpem.br` is CNPEM-network-only); the single exception is Manaca, whose MX topology is public via its MXCuBE hardware-object config in `cnpem/mxcubeweb-lnls`. A one-beamline fleet produces no cross-beamline recurrence signal, so this report is a curated single-beamline summary, not a frequency table. Re-generate when a second Sirius beamline is device-passed.

## Family mapping (Manaca, curated)

Manaca is a kappa-geometry MX beamline (serial + room-temperature). Every device maps to an already-graduated catalog Family or Assembly; the MXCuBE service objects are orchestration / LIMS seam, not Assets. See `beamlines/manaca/facts.md` for the full per-device mapping with EPICS handles.

| Catalog Family | Manaca devices | Status |
| --- | --- | --- |
| Goniometer | MD kappa goniometer (omega/kappa/kappaphi/phiy/phiz/sampx/sampy/sampz) | graduated (i03) |
| PseudoAxis | energy / wavelength / resolution over the DCM | graduated |
| Camera | on-axis sample-view (`LNLSCamera`) | graduated |
| LinearStage | detector-distance | graduated |
| InsertionDevice | APU22 undulator phase (sector 09SA) | graduated |
| TemperatureController | cryostream (`MNC:CRYCON:RTEMP`) | graduated |
| FluxMonitor | Cividec diamond flux monitor | graduated |
| Filter | transmission / attenuation | graduated |
| Shutter | PPS safety shutter | graduated |
| Objective | on-axis-view zoom | graduated |
| Backlight | sample-illumination back/front lights | graduated |
| EnergyDispersiveSpectrometer | XRF fluorescence readout (no handle; confirm) | graduated |
| Positioner | 48-pin sample-changer robot (`MNC:B:ROBCS801:`) | graduated (role-as-family; robot folds here) |

## Graduation shortlist (the actionable output)

**Zero new families.** Manaca is pure reuse of the MX vocabulary already graduated at i03 / the NSLS-II MX fleet plus the robot-as-Positioner pattern. No signal toward any new Family from a single MX beamline.

Notable for the cross-facility picture: the **sample-changer robot** here folds to Positioner + Clearance + Subject custody rather than a SampleChanger Family, the same decision reached at ALBA XALOC, SOLEIL PX1, SESAME, and the NSLS-II / Diamond MX beamlines. Manaca reinforces it at yet another facility and its first Bluesky (sophys) control plane.

## Provenance

Extracted by `scripts/reverse_engineer --source mxcube` from the public `cnpem/mxcubeweb-lnls` MXCuBE config (26 devices, 18 MXCuBE software-service rows filtered), then human-curated (family mapping in `facts.md`). Unlike ALBA / SOLEIL (classic XML in upstream `mxcubecore`), Manaca uses the newer per-device YAML HardwareObjects format, so this pass added a YAML reader to the extractor's `--source mxcube` path. Real EPICS handles verified verbatim (`MNC:` = Manaca; `SI-09SA:ID-APU22` = the sector 09SA undulator). The raw machine-frequency table the extractor emits for a single beamline is not meaningful (every class appears once); this curated summary supersedes it.
