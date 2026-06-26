# Open questions

*What CORA needs the SIX team to confirm before the model can be trusted.*

SIX was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/six-profile-collection](https://github.com/NSLS2/six-profile-collection)), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from the `startup/*.py` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet), including the new loose families). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | Does SIX share a canted straight with a sibling beamline, or run off its own undulator in series? | One root Unit Asset `SIX` on its own EPU straight. | The source topology in the [descriptor](inventory.md). |
| ENC-1 | Blocks-go-live | Are the PV zones `XF:02IDA/B/C/D` four separate shielded hutches or beam zones within fewer hutches? | Four enclosures, one per zone. | The Enclosure grouping. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the six-profile-collection current and correct? | The handles in the descriptor are taken from the profile collection and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals for the hutches. | Permit leaves to be named; the photon shutters are `XF:02ID-PPS{Sh:FE}` / `XF:02IDA-PPS{PSh}` / `XF:02IDB-PPS{PSh}`. | The Enclosure permit signals. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The EPU (`SR:C02-ID:G1A{EPU:1}`): type, period, and the polarization (phase) model. | One `InsertionDevice` Asset; the phase axis carried as a setting. | The insertion-device spec. |
| MONO-1 | Blocks-build | The plane-grating monochromator: energy range, the three grating line densities (500 / 1200 / 1800 l/mm), and the c-value (cff) model. | A `GratingMonochromator` Asset (catalog Family) with energy / cff / grating-pitch / premirror-pitch / grating-translation axes. | The monochromator energy and grating model. |
| OPT-1 | Nice-to-have | The mirrors (M1, M3, M4, M5, M6): coatings, stripes, and the hexapod / bender axis roles. | `Mirror` Assets with the config's PV roots; coatings unconfirmed. | The mirror specs. |
| OPT-2 | Nice-to-have | The baffle slits, the exit slit, and the M5 mask: the internal axis maps. | `Slit` / `Aperture` Assets with base PVs; per-blade axes partial. | The slit and aperture axis maps. |

## RIXS endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| RIXS-1 | Blocks-build | The spectrometer-arm geometry: the bridge truss (`BT:1`), the in-arm optics chamber (`3AA:1`), and the detector chamber (`DC:1`): which axis is the arm scattering angle, the dispersion, and the detector distance, and how the arm pivots about the sample chamber. | One loose `SpectrometerArm` Asset with the three chambers' axes; the sample chamber as the pivot. | The spectrometer model and whether it composes into an Assembly. |
| RIXS-2 | Nice-to-have | The RIXS camera (`XF:02ID1-ES{RIXSCam}`): the sensor, the photon-counting / centroiding pipeline, and the curvature correction. | One `Camera` Asset; the centroiding behavior carried as a note. | The detector model and Family decision. |
| DET-1 | Nice-to-have | The counting scaler, the Femto electrometer, and the camera readout: which channels are I0 versus signal. | `FluxMonitor` Assets plus the `Camera`. | The detector channel map. |
| DIAG-1 | Nice-to-have | The DIAGON diagnostic (`XF:02IDA-OP{Diag:1`): is it a polarization diagnostic, and what does it report? | One `GenericProbe` Asset (placeholder classification). | The diagnostic classification and Family. |

## Sample environment and supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The UHV cryostat manipulator (`SC:1-Cryo:S1_B`) and the Lakeshore controller: the cryo temperature range, the base pressure, and any load-lock / sample-transfer mechanism. | A `Manipulator` Asset (catalog Family, x/y/z/theta) plus a `TemperatureController`. | The sample-environment model. |
| SUP-1 | Nice-to-have | The vacuum and cryogen supplies the UHV optics, the spectrometer arm, and the cryostat draw on. | Photon beam, cooling water, and vacuum carried in the descriptor. | The Supply records. |
