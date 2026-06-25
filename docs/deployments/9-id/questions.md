# Open questions

*What CORA needs the 9-ID team to confirm before the model can be trusted.*

9-ID was reverse-engineered from the beamline's own Bluesky instrument repo ([BCDA-APS/9id_bits](https://github.com/BCDA-APS/9id_bits)), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from a config snapshot rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet), including the metadata seam and the loose families held for gate-review). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | Do the two stations (`9-ID-A`, `9-ID-D`) run off one beam in series, and is there a single undulator or a canted pair? The config showed one undulator (`S09ID:DSID:`) and `9-ID-A` / `9-ID-D` prefixes. | One root Unit Asset `9-ID` with one optics spine feeding 9-ID-D in series; one undulator. | The beam walk and station count in the [descriptor](inventory.md). |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the 9id_bits config current and correct? | The handles in the descriptor are taken from the config and carried confirm. | Verifying each Asset's control handle. |
| CTRL-2 | Nice-to-have | The fly-scan timing: the multi-channel scaler (`9idCSSI:mcs2-01`) and any pulse routing that gates the grazing-incidence scans. | One `GenericProbe` scaler is modelled; the timing graph is not. | The fly-scan timing model. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals for the two hutches (`9-ID-A`, `9-ID-D`). | Two hutches exist with permit signals to be named. | The Enclosure permit signals. |

## Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The undulator on S09ID: type, period, and whether a second device or a canted pair exists. | One `InsertionDevice` Asset; period unconfirmed. | The insertion-device spec. |
| MONO-1 | Blocks-go-live | The Kohzu monochromator (`idt_mono`, `9ida:`): energy range, crystal set, and per-axis roles. | One `Monochromator` Asset; range unconfirmed. | The monochromator energy model. |
| OPT-1 | Nice-to-have | The two FMBO mirrors: coatings and the bender / piezo-pitch axis roles. | Two `Mirror` Assets with the config's axis maps; coatings unconfirmed. | The mirror specs. |
| OPT-2 | Nice-to-have | The white-beam apertures (`SL-1`, `SL-2`) and the guard slits (`Slit3/4/5`): the internal axis maps. | `Aperture` and `Slit` Assets with base PVs; per-blade axes partial. | The aperture and slit axis maps. |
| OPT-3 | Blocks-go-live | The JJ CRL transfocator (`9idPyCRL:CRL9ID:`): lens material, count, and which stations it focuses. | One `Transfocator` Asset (loose Family). | The transfocator spec. |
| OPT-4 | Nice-to-have | The AVS attenuator (`9idPyFilter:FL1:`): the foil / absorber set. | One `Filter` Asset. | The attenuator model. |
| OPT-5 | Nice-to-have | The KB focusing pair (`9idKB:`): the per-mirror bender axes and the focal geometry (capacitive-sensor suffixes resolved at runtime). | One `Mirror` Asset with four bender axes plus a granite support. | The KB axis map. |

## Sample

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CSSI-1 | Blocks-build | The grazing-incidence sample geometry: which motor sets the incidence angle, and the translation-vs-rotation roles of the CSSI stack (`9idCSSI:mcs2-01`, the Aerotech fly Z, the Kohzu stage). | A `LinearStage` for translation and a `RotaryStage` for the incidence angle; the Kohzu stage folded into a note. | The sample geometry and whether it composes into an Assembly. |
| CSSI-2 | Nice-to-have | The two Aerotech hexapods (`HP1`, `HP2`): what each aligns (sample, KB, detector). | Two `Hexapod` Assets for sample/optic alignment. | The hexapod roles. |
| CSSI-3 | Nice-to-have | The viewing microscope (`uscope`, `9idCSSI:CR9D1M2`): on-axis sample viewing or a separate optic. | One `Camera` Asset for sample viewing. | The microscope role. |

## Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The area detectors: the Pilatus 1M (`PILATUS_1MF:`), the Eiger (prefix a guess), and the WAXS / GIWAXS detector on its pedestal: models, sensors, frame rates. | `Camera` Assets; models unconfirmed. | The detector Model bindings. |
| BPM-1 | Nice-to-have | The TetrAMM (`9idTetra:QUAD1:`) and the two XBPMs (`xpbm1`, `xpbm2`): which are position monitors versus intensity (I0) normalizers? | Bound to a loose `BeamPositionMonitor` Family presenting the Sensor Role. | The monitor classification. |
| DIAG-1 | Nice-to-have | The diagnostic flag cameras (`flag1-3`) and the DAMM mask (`9ida:CR9A1`): what each is, and whether the flags carry cameras CORA should model. | Folded into a descriptor note; not modelled as Assets (only insertion motors extracted). | The diagnostic identification. |

## Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | Nice-to-have | The vacuum and process-gas supplies the focusing optics and detector flight draw on. | Photon beam, cooling water, and vacuum carried in the descriptor. | The Supply records. |
