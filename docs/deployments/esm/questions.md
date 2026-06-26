# Open questions

*What CORA needs the ESM team to confirm before the model can be trusted.*

ESM was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/esm-arpes-profile-collection](https://github.com/NSLS2/esm-arpes-profile-collection)), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from the `startup/*.py` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet), including the `Manipulator` graduation and the deferred XPEEM branch). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The two EPUs (EPU57 on G1A, EPU105 on G1B): periods, the polarization (phase) model, and how the pair is coordinated. | Two `InsertionDevice` Assets; the phase axis carried as a setting. | The insertion-device specs. |
| ENC-1 | Blocks-go-live | Are the PV zones `XF:21IDA/B/C/D` separate shielded hutches or beam zones within fewer? | Four enclosures, one per zone. | The Enclosure grouping. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals for the hutches. | Permit leaves to be named; shutters are `XF:21ID-PPS{Sh:FE}` / `XF:21IDA-PPS{PSh}` / `XF:21IDC-PPS{PSh:1A/1B}`. | The Enclosure permit signals. |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the esm-arpes-profile-collection current and correct? | The handles in the descriptor are taken from the profile collection and carried confirm. | Verifying each Asset's control handle. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MONO-1 | Blocks-go-live | The PGM: the grating line densities, the c-value model, and the energy range. | A `GratingMonochromator` Asset (catalog Family) with energy / focus-const / grating-pitch / mirror-pitch / grating-translation axes. | The monochromator model. |
| OPT-1 | Nice-to-have | The mirrors (M1, M3 hexapod, M4A KB pair, M4B hexapod): coatings and axis roles. | `Mirror` Assets with the config's PV roots; coatings unconfirmed. | The mirror specs. |
| OPT-2 | Nice-to-have | The PGM slits, the M3 slit, and the A/B exit slits: the internal axis maps. | `Slit` Assets with base PVs; per-blade axes partial. | The slit axis maps. |
| DIAG-1 | Nice-to-have | The ESM Diagon (`XF:21IDA-OP{Diag:1`): is it a polarization diagnostic, and what does it report? | One `GenericProbe` Asset (placeholder classification). | The diagnostic classification. |

## ARPES endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ARPES-1 | Blocks-build | The Scienta SES analyzer (`XF21ID1-ES-SES`): the model, the lens modes, the pass-energy and kinetic-energy-window controls, and the acquisition modes. | An `ElectronAnalyzer` Asset (catalog Family) presenting the Detector Role. | The analyzer model and lens / pass-energy controls. |
| SAMPLE-1 | Blocks-go-live | The LT UHV cryostat manipulator: the live prefix (the config shows a provisional `{PRV` and a commented `{LT:1-Manip:EA5_1`), the six axes, the cryo range, and the sample-prep / load-lock chambers. | A `Manipulator` Asset (x/y/z + Rx/Ry/Rz) plus a `TemperatureController`. | The sample-environment model. |
| DET-1 | Nice-to-have | The QuadEM flux monitors (qem01-12): which are I0 versus drain-current, and where each sits. | Two representative `FluxMonitor` Assets; the full set summarized. | The flux-monitor map. |

## Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | Nice-to-have | The vacuum and cryogen supplies the UHV optics, the analyzer, and the cryostat draw on. | Photon beam, cooling water, and vacuum carried in the descriptor. | The Supply records. |
