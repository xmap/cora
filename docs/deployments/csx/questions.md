# Open questions

*What CORA needs the CSX team to confirm before the model can be trusted.*

CSX was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/csx-profile-collection](https://github.com/NSLS2/csx-profile-collection)), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from the `startup/csx1` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet), including the `GratingMonochromator` graduation). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | The 23-ID canted straight: do the two EPUs feed CSX (23-ID-1) plus a sibling branch, and is CSX one root Unit? | One root Unit `CSX` fed by the canted twin-EPU straight (the 32-ID precedent). | The source topology in the [descriptor](inventory.md). |
| ENC-1 | Blocks-go-live | Are the PV zones `XF:23IDA` / `XF:23ID1-OP` / `XF:23ID1-ES` separate shielded hutches or beam zones within fewer? | Two enclosures (front-end optics + the 23-ID-1 branch). | The Enclosure grouping. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the csx-profile-collection current and correct? | The handles in the descriptor are taken from the profile collection and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals for the hutches. | Permit leaves to be named; the front-end shutter is `XF:23ID1-PPS{Sh:FE}`. | The Enclosure permit signals. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The two EPUs (`EPU:1`, `EPU:2`): type, period, and the polarization (phase) model. | Two `InsertionDevice` Assets; the phase axis carried as a setting. | The insertion-device specs. |
| MONO-1 | Blocks-go-live | The VLS-PGM: the grating line densities, the c-value model, and the 200-2200 eV range. | A `GratingMonochromator` Asset (catalog Family) with energy / mirror-pitch / mirror-x / grating-pitch / grating-x axes. | The monochromator model. |
| OPT-1 | Nice-to-have | The mirrors (M1A front-end hexapod, M3A refocusing): coatings and axis roles. | `Mirror` Assets with the config's PV roots; coatings unconfirmed. | The mirror specs. |
| OPT-2 | Nice-to-have | The branch slits (`Slt:1` / `Slt:2` gap-center, `Slt:3` x/y): the internal axis maps. | `Slit` Assets with base PVs; per-blade axes partial. | The slit axis maps. |

## TARDIS endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-build | The TARDIS E6C geometry: confirm the circle roles (theta, delta, gamma, mu) and which is sample versus detector. | A 6-circle hkl E6C diffractometer binding the `Goniometer` Family + the `Assembly(Diffractometer)`. | The circle geometry and the Assembly binding. |
| DIFF-2 | Blocks-go-live | The reciprocal-space coordination: the hkl E6C inverse-kinematics over this geometry. | A `PseudoAxis` Asset for the reciprocal-space layer. | The pseudo-axis model. |
| SAMPLE-1 | Nice-to-have | The sample stage, the holography stage, and the cryostat: the axes, the cryo range, and the fine nanopositioner. | A `LinearStage` (sx / say / saz + holography) and a `TemperatureController`. | The sample-environment model. |

## Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The coherent detectors (FastCCD, AXIS), the scaler / MCS, and the diode: models, sensors, and channels. | `Camera` Assets, a `FluxMonitor` scaler, and a `GenericProbe` diode. | The detector models and channel map. |

## Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | Nice-to-have | The vacuum and cryogen supplies the UHV optics, the in-vacuum TARDIS, and the cryostat draw on. | Photon beam, cooling water, and vacuum carried in the descriptor. | The Supply records. |
