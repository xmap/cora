# Open questions

*What CORA needs the 8-ID team to confirm before the model can be trusted.*

8-ID was reverse-engineered from the beamline's own Bluesky instrument repo ([BCDA-APS/8id-bits](https://github.com/BCDA-APS/8id-bits)), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from a config snapshot rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet), including the catalog graduation and the diffractometer Assembly). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | Are the two undulators canted feeding separate branches, and do the four stations (`8-ID-A/D/E/I`) run off one beam in series or split? | One root Unit Asset `8-ID` with one optics spine feeding the stations in series. | One-vs-many beam walks in the [descriptor](inventory.md). |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the 8id-bits config current and correct? | The handles in the descriptor are taken from the config and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals for the four hutches. | Four hutches exist with permit signals to be named. | The Enclosure permit signals. |

## Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The two undulators (downstream DSID, upstream USID): types, periods, and whether canted. | Two `InsertionDevice` Assets; periods unconfirmed. | The insertion-device specs. |
| MONO-1 | Blocks-go-live | The MN1 monochromator energy range and crystal. | One `Monochromator` Asset (8idaSoft:MN1); range unconfirmed. | The monochromator energy model. |
| MONO-2 | Nice-to-have | The in-line `idt_mono` (8idaSoft:MONO): is it a second monochromator or a different optic? | Not modelled in this cut. | Whether it becomes a second Asset. |
| OPT-1 | Nice-to-have | The two FMBO mirrors: coatings and the bender / piezo-pitch axis roles. | Two `Mirror` Assets with the config's axis maps; coatings unconfirmed. | The mirror specs. |
| OPT-2 | Nice-to-have | The slit internal axis maps (most slits carried only a base PV in the config). | `Slit` Assets with base PVs; per-blade axes partial. | The slit axis maps. |
| OPT-3 | Blocks-go-live | The two CRL transfocators (rl1, rl2): lens material and the per-lens actuator roles (ten lenses each). | Two `Transfocator` Assets; x/y/pitch/yaw mapped, the ten lens actuators summarized. | The transfocator spec. |

## Diffractometer

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-build | The six-circle Huber geometry: confirm the circle roles (mu, eta, chi, phi, nu, delta) and which is sample versus detector arm. | A six-circle diffractometer modelled as a plain device with the config's axis map; this confirms the `Assembly(Diffractometer)` slot shape. | The circle geometry and the Assembly slots (see [Model](model.md#deliberately-not-here-yet)). |
| DIFF-2 | Blocks-go-live | The reciprocal-space coordination: is hklpy2 driving an (h, k, l, energy) pseudo-axis over this geometry? | A `PseudoAxis` Asset (psic) is modelled for the reciprocal-space layer. | The pseudo-axis model. |

## Sample environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TEMP-1 | Nice-to-have | The LakeShore 336 controllers and the Quantum Northwest holders: sensor channels and the sample stages they regulate. | `TemperatureController` Assets at 8-ID-E and 8-ID-I. | The temperature-controller model. |
| SAMPLE-1 | Nice-to-have | The rheometer shear-cell: the six axes and the shear modes it supports. | One `Rheometer` Asset (loose Family) with a six-axis map. | The rheometer model. |
| SAMPLE-2 | Nice-to-have | The UR5 robotic sample changer (RobocartUR5): is it CORA-driven, and what is its sample-exchange model? | Deferred; not modelled (CORA has no sample-changer shape). | The sample-changer model. |

## Detector and XPCS

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The three area detectors (Eiger 4M, Lambda 2M, Rigaku 3M): models, sensors, and frame rates. | Three `Camera` Assets; models unconfirmed. | The detector Model bindings. |
| BPM-1 | Nice-to-have | The Sydor beam-position monitor and the four TetrAMM channels: which are position monitors versus intensity (I0) normalizers? | Bound to a loose `BeamPositionMonitor` Family presenting the Sensor Role. | The monitor classification. |
| XPCS-1 | Nice-to-have | The fast shutter timing and its role in the XPCS exposure sequence. | One `Shutter` Asset (8ideSoft:fastshutter). | The fast-shutter model. |
| XPCS-2 | Nice-to-have | The flight-path geometry (length, swing) and the beam-stop relationship. | One `FlightPath` Asset (loose Family) plus a `BeamStop`. | The flight-path model. |
| XPCS-3 | Nice-to-have | The softGlue FPGA timing graph (8idMZ1): the signal routing for detector gating. | One `TimingController` Asset; the signal graph is not modelled. | The timing model. |

## Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | Nice-to-have | The vacuum and process-gas supplies the flight path and sample environments draw on. | Photon beam, cooling water, and vacuum carried in the descriptor. | The Supply records. |
