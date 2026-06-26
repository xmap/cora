# Open questions

*What CORA needs the ISS team to confirm. This model is reverse-engineered from public open source (the `NSLS2/iss-profile-collection` bluesky / ophyd startup files): the EPICS PVs are read from the `startup/*.py` device classes, but undulator parameters, crystal cuts, vendor identities, and physical positions are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The 8-ID insertion-device identity, period, and gap range. The profile collection drives photon energy through the HHM trajectory and does not expose the undulator gap PVs; only the ring current (`SR:OPS-BI{DCCT:1}`) is read. | An in-vacuum undulator on the 3 GeV ring, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the shutters (`XF:08ID-PPS{Sh:FE}`, `XF:08IDA-PPS{PSh}`) are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The HHM and HRM crystal cuts, reflections, and energy ranges. Both monochromators (`Mono:HHM`, `Mono:HRM`) and the HHM trajectory controller (`MC:06`) are in source. | One trajectory DCM and one high-resolution mono Asset, crystal settings blank. | The Monochromator settings. |
| ENERGY-1 | Nice-to-have | ISS's measurement sweeps the energy axis (EXAFS) as a trajectory fly-scan, the textbook case for the energy-scan Capability the catalog anticipates. Does CORA coin `energy_scan` now, or keep it deferred until a conduct-path forces it? | Energy-scan deferred (the BMM question); ISS is a further consumer that strengthens the case. | The energy-scan Capability decision. |

## Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SPEC-1 | Blocks-go-live | The Johann and von Hamos crystal emission spectrometer geometry: the analyzer crystal cut, the Rowland-circle radius, and whether each of the (Johann: main + four auxiliary) analyzer crystals is a child Asset or a setting on the one spectrometer Asset. | Two `EmissionSpectrometer` Assets (catalog Family, graduated at this 2nd sighting after LCLS-MFX); crystals as settings for now. | The emission-spectrometer model and analyzer-crystal composition. |
| DET-1 | Blocks-go-live | The detector roster: the ion-chamber channel map (I0 / It / Ir / If through the ICAmplifier / Keithley-428 amps and the analog pizza box), the Xspress3 element count and ROI map, and which Pilatus serves which spectrometer. | The ion chambers, the 4-channel Xspress3, and one Pilatus modelled; channel maps blank. | The detector roster and channel maps. |
| TEMP-1 | Nice-to-have | Which sample-environment thermal units are live (the Lakeshore 331 is in source; cryostat / furnace not). | One `TemperatureController` Asset; the others noted. | The sample-environment Assets. |
| ENV-1 | Nice-to-have | The ion-chamber fill-gas flow (He / N2 mass-flow controllers `XF:08IDB-OP{IC}FLW:`) and the broader in-situ sample environment. None fits a catalog family cleanly (the loose FlowController). | Deferred; fill gas and in-situ environment named here, not modelled. | The fill-gas and in-situ Assets. |
| DIAG-1 | Nice-to-have | The beam-position channel map (the Prosilica BPM cameras and the sample-positioner cameras) and the `BeamPositionMonitor` sensor fold-vs-promote hold. | Read-only beam-position (loose `BeamPositionMonitor`) probes; channel map blank. | The BeamPositionMonitor bindings. |

## Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, and IPs (the Delta-Tau HHM trajectory controller `MC:06`, the von Hamos `MC:3-Ax:` axes, and the EPICS motor records). | Families bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the X-ray absorption (EXAFS) and X-ray emission (XES / HERFD) techniques enter CORA's catalog as Methods, or stay pending? ISS reuses the `xas_spectroscopy` Method LCLS-MFX left pending, the second consumer. | The `xas_spectroscopy` Method reused pending; no new Method coined (the BMM / SST deferral discipline). | The technique Method scope. |
