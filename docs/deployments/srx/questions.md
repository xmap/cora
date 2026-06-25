# Open questions

*What CORA needs the SRX team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/srx-profile-collection`](https://github.com/NSLS2/srx-profile-collection) profile collection): the EPICS PVs are read from it, but vendor identities, physical positions, and the detector/endstation configuration are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | IVU21 undulator period, gap range, and harmonic usage. The device (`SR:C5-ID:G1{IVU21:1}`) is confirmed. | An in-vacuum undulator, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the shutters (`XF:05ID-PPS{Sh:WB}`, `05IDA-PPS:1{PSh:2}`, `05IDB-PPS:1{PSh:4}`) are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | The hutch layout: which PV zones (05IDA optics, 05IDB micro endstation, 05IDD nano endstation) are distinct enclosures? | Two enclosures, optics + experiment (nano). | The Enclosure set and roles. |

## Optics and sample

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The HDCM crystal cut and energy range. | High-heat-load DCM, range blank. | The Monochromator settings. |
| STAGE-1 | Blocks-go-live | The XRF-tomography sample rotation hardware, encoder resolution, and max speed. | A RotaryStage, specs blank. | The SampleRotary settings. |
| ENDSTATION-1 | Nice-to-have | The micro endstation (05IDB): is it a distinct sample stack from the nano endstation modelled here, and how are the two selected? | The nano (KB) endstation is modelled; the micro endstation is noted, deferred. | The micro-endstation Assets. |

## Detectors and controls

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The Xspress3 fluorescence detector element count and vendor. | One `EnergyDispersiveSpectrometer` Asset presenting the Sensor Role; specs blank. | The detector Model and element count. |
| CAM-1 | Blocks-go-live | Which pixel/area detectors are live vs legacy? Source has Merlin, Dexela, Eiger 1M, a PCO imaging camera, and legacy detectors. | Merlin/Dexela/Eiger/PCO modelled as Cameras; legacy excluded. | The detector roster and per-technique detector slot. |
| DIAG-1 | Nice-to-have | The scaler / ion-chamber flux channel map (which channel is I0). | Read-only flux counters (`FluxMonitor`), channel map blank. | The FluxCounter bindings. |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, IPs. | Families bound (MotionController), specifics blank. | The MotionController Models. |
| ENERGY-1 | Nice-to-have | Does SRX's XANES sweep warrant the `energy_scan` Capability the catalog anticipates (shared with BMM), or stay under `characterization`? | XANES mapped to existing Capabilities; energy_scan deferred (the BMM question). | The spectroscopy Capability decision. |
