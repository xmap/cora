# Open questions

*What CORA needs the IOS team to confirm before the model can be trusted.*

IOS was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/ios-profile-collection](https://github.com/NSLS2/ios-profile-collection)), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from the `startup/*.py` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | The 23-ID canted straight: do the two EPUs feed both CSX (23-ID-1) and IOS (23-ID-2), and is IOS one root Unit? | One root Unit `IOS` fed by the canted twin-EPU straight (the 32-ID / CSX precedent). | The source topology in the [descriptor](inventory.md). |
| ENC-1 | Blocks-go-live | Are the PV zones `XF:23IDA` / `XF:23ID2-OP` / `XF:23ID2-ES` separate shielded hutches or beam zones within fewer? | Two enclosures (front-end optics + the 23-ID-2 branch). | The Enclosure grouping. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the ios-profile-collection current and correct, and is a queue server in use? | The handles in the descriptor are taken from the profile collection and carried confirm; queue-server use unknown. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals for the hutches. | Permit leaves to be named; the front-end shutter is `XF:23ID-PPS{Sh:FE}` and the branch shutter `XF:23ID2-PPS{PSh}`. | The Enclosure permit signals. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The two EPUs (`EPU:1`, `EPU:2`): type, period, the polarization (phase) model, and the energy-edge lookup tables. | Two `InsertionDevice` Assets; the phase axis and the edge table carried as settings. | The insertion-device specs. |
| MONO-1 | Blocks-go-live | The VLS-PGM: the grating line densities, the c-value model, and the 200-2200 eV range. | A `GratingMonochromator` Asset with energy / mirror-pitch / mirror-x / grating-pitch / grating-x axes and an energy fly-scan. | The monochromator model. |
| OPT-1 | Nice-to-have | The mirrors (M1A front-end, M1B1 / M1B2 deflecting, M3B branch, DM1, the KB pair): coatings and axis roles. | `Mirror` Assets with the config's PV roots; coatings unconfirmed. | The mirror specs. |
| OPT-2 | Nice-to-have | The branch slits (`Slt:1` gap-center, `Slt:2` vertical): the internal axis maps. | `Slit` Assets with base PVs; per-blade axes partial. | The slit axis maps. |

## Sample and ambient-pressure environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-build | The APPES manipulator (x / y / z / rotation) and the IOXAS stage: the axis roles, and the sample-transfer / load-lock mechanism (the `IOXAS-GV:4` valve is present, no transfer-motor PVs are). | A `Manipulator` and a `LinearStage`; the transfer mechanism deferred. | The sample-positioning model. |
| SAMPLE-2 | Nice-to-have | The SPECS surface-prep sputter / ion gun: control and role. | A `GenericProbe` auxiliary, not the analyzer. | The surface-prep model. |
| INSITU-1 | Blocks-build | The ambient-pressure reaction cell, the gas dosing / mixing manifold, the pressure control, and the sample heating: there are no gas / pressure / temperature PVs in the profile collection. | The ambient-pressure sample environment is out of the profile collection and not modelled until the hardware and PVs are provided. | The operando sample environment, IOS's defining feature. |

## Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The SPECS hemispherical analyzer: model (Phoibos NAP?), pass-energy range, lens-mode set, and angular acceptance. | An `ElectronAnalyzer` Asset; analyzer make and ranges are settings. | The analyzer model. |
| DET-2 | Blocks-go-live | The Vortex and Xspress3 silicon-drift detectors: models, channels, and the ROI map (and why one of four Xspress3 channels is active). | `EnergyDispersiveSpectrometer` Assets; ROI / channel maps partial. | The fluorescence-detector models. |
| DET-3 | Nice-to-have | The scaler, the `CurrAmp:1/2/3` current amplifiers, and the Au mesh: the electron-yield (TEY / PEY) channel wiring and the I0 reference. | `FluxMonitor` Assets; the yield-chain wiring partial. | The yield-chain map. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENERGY-1 | Nice-to-have | Is the NEXAFS / XAS measurement a continuous PGM energy fly-scan (with coupled EPU edge-table switching) or a stepped scan? | The PGM energy fly-scan is available; the sweep-as-measurement is carried as intent. | The energy-scan mode. |

## Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | Nice-to-have | The vacuum and cooling supplies the UHV optics, the KB system, and the analyzer endstation draw on. | Photon beam, cooling water, and vacuum carried in the descriptor. | The Supply records. |
