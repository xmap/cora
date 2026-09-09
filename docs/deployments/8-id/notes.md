# Notes

## Techniques

*What the modelled part of 8-ID is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. 8-ID's signature technique, **XPCS, is now a catalog Method** (`cora.capability.xpcs`): it is the second beamline after LCLS-MFX to need a DAQ-owned high-rate frame stream, which graduated XPCS out of the imaging-heritage catalog. Small-angle scattering and six-circle diffraction stay pending until they enter scope (`TECH-1`).

### X-ray photon correlation spectroscopy

XPCS measures the time correlations of a coherent speckle pattern to probe sample dynamics, so it records long, fast time series on an area detector under a precisely gated exposure.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| XPCS | [`xpcs`](../../catalog/methods.md) | coherent-scattering intensity time series on the Eiger / Lambda / Rigaku detectors, gated by the softGlue timing; now a catalog Method. Its acquisition is a DAQ-owned high-rate frame stream with no executing body yet, the [event-stream acquisition axis](#deliberately-not-here-yet) (Stage 1) |
| Small-angle scattering | `small_angle_scattering` | static SAXS on the same detectors; a Plan setting over the same chain |

Both need the [XPCS sample stage](sample.md), the [coherent detectors](detector.md), and the flight path. The fast shutter and softGlue timing (`XPCS-1`, `XPCS-3`) gate the exposure.

### Six-circle diffraction

The 8-ID-E Huber diffractometer orients a single crystal through six circles and scans reciprocal space, sharing the diffraction Method with 4-ID.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Six-circle diffraction | `diffraction` | reciprocal-space scans on the six-circle Huber; shares the 4-ID `diffraction` Method (`TECH-1`) |

It needs the [diffractometer](sample.md). The reciprocal-space coordination is `DIFF-2`; the reusable `Assembly(Diffractometer)` is on [Model](#deliberately-not-here-yet).

### Not modelled yet

The XPCS Method now exists, but the concrete acquisition primitive that executes it (a DAQ-owned high-rate frame stream, not a poll-to-Done capture) does not: that is the [event-stream acquisition axis](#deliberately-not-here-yet), now at Stage 1 (8-ID XPCS is its second beamline after LCLS-MFX). Small-angle scattering and diffraction Methods remain an owner-scope decision (`TECH-1`); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at 8-ID, and the trust shape that will gate it. First cut.*

Governance at 8-ID follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

8-ID is not yet driven by CORA, so this shape is not yet instantiated. The 8-ID operator pool and beamline-scientist assignments are not modelled ahead of confirmation (a placeholder `8-ID Beamline Scientist` is carried pending on the [APS Site](../aps/index.md#safety-and-governance)).

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [APS Site](../aps/index.md#safety-and-governance), not on the beamline, and the beamline links up to them. 8-ID adds hazard classes beyond the imaging envelope, cryogens at the temperature-controlled sample environments and the user-brought rheometer and robotic sample changer, that an experiment Clearance would carry; those land with the instruments that bring them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives 8-ID, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's 8-ID content lives, the XPCS deployment that added the `xpcs` Method and landed the Diffractometer Assembly, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 8-ID |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Loose families held for gate-review

8-ID adds a second independent APS beamline (after 4-ID POLAR) to three device classes that recur widely: `TemperatureController`, `Transfocator`, and `PositionMonitor`. All three have since graduated to catalog Families. `TemperatureController` graduated when the parallel Diamond i22/i03/i11 rule-of-three settled the settable-actuator abstraction (`ENV-1`), and it presents the new `Regulator` Role. `Transfocator` graduated as a CRL focusing optic Family, distinct from `Mirror` / `ZonePlate` / `Condenser`: it is bound across several beamlines (APS 4-ID/8-ID/9-id, Diamond i22, NSLS-II chx/smi/ixs, SLAC lcls-mfx), and the cross-facility review settled it as the CRL-specific home rather than a general focusing optic. `PositionMonitor` graduated as its own catalog Family presenting the `Sensor` Role, earned across the wide fleet that shares it (APS 4-ID/8-ID/9-ID, the NSLS-II beamlines, and the imaging and MX beamlines), distinct from the graduated `FluxMonitor` by what it measures: beam position and centroid, not flux or intensity. The still-loose `Diagnostic` family (arrival-time and photon-spectrum monitors) stays loose, a separate abstraction that measures timing and spectrum rather than position; only the per-Asset beam-center calibration and the position-versus-intensity channel split stay open (`DIAG-1`).

| Loose family | Presents (when graduated) | At 4-ID | At 8-ID |
| --- | --- | --- | --- |
| `PositionMonitor` | Sensor | XBPM / Sydor / TetrAMM | Sydor (8-ID-E) + TetrAMM (8-ID-I) |

`Transfocator` and `TemperatureController` were tracked here too and have since graduated to catalog Families. `Transfocator` is the CRL focusing optic Family the two 8-ID-D lens stacks bind (the lens material and lenslet count stay open, `OPT-3`). `TemperatureController` (#350) presents the `Regulator` Role (the LakeShore 336 at 8-ID-E and the Quantum Northwest holders at 8-ID-I bind it). Neither is held for gate-review any longer.

`Magnet` was tracked here too on a single physical beamline (4-ID; `6idb-bits` is a 4-ID fork, see the [4-ID model page](../4-id/notes.md#deliberately-not-here-yet)); it has since graduated to a catalog Family on the 4-ID + i10-1 + ID32 rule-of-three (it presents the `Regulator` Role). `Preamplifier` stays loose on that single physical beamline.

### The Diffractometer Assembly (landed)

The `Assembly(Diffractometer)` designed during the catalog-graduation pass is now real, and it **composes the `Goniometer` Family** that landed for I03 MX (#340) rather than re-modelling the sample circles. It is in [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) as a flat assembly presenting the Positioner Role, with slots `goniometer` (Goniometer, `Exactly1`, the sample-orientation circles plus centring), `detector_arm` (RotaryStage, `ZeroOrMore`, spanning 8-ID's nu / delta and 4-ID's detector-arm-less geometries), and `reciprocal_space` (PseudoAxis, whose partition rule resolves the hklpy2 inverse kinematics). The distinction from the Goniometer Family is deliberate: the Goniometer is the integrated single-device sample orienter (the I03 Smargon); the Diffractometer is the larger composed scattering instrument that USES one. The integration scenario [`test_8id_diffractometer_setup.py`](https://github.com/xmap/cora/blob/main/apps/api/tests/integration/scenarios/test_8id_diffractometer_setup.py) materializes it end-to-end against Postgres: it installs the four 8-ID-E constituent Assets (a Goniometer for mu / eta / chi / phi, the nu / delta detector-arm circles, and the reciprocal-space axis), defines the Assembly, and registers a Fixture binding the two detector circles to the `detector_arm` slot. The circle-role confirmation remains `DIFF-1` and the reciprocal-space solver rule is `DIFF-2`; the 4-ID Fixture is the follow-on (the Assembly is shared, the Fixture is per-beamline).

### Deliberately not here yet

- **The UR5 robotic sample changer.** `RobocartUR5` is a user-brought robotic arm; CORA has no sample-changer shape (the same gap the 32-ID projection-microscope changer raised). It is not modelled (`SAMPLE-2`).

- **The softGlue timing graph.** The XPCS exposure timing runs on a softGlueZynq FPGA fabric (`8idMZ1:`); it is modelled coarsely as one `TimingController`, not as its full signal graph (`XPCS-3`).

- **The event-stream acquisition axis (the XPCS execution).** The `xpcs` Method is now in the catalog, but the acquisition primitive that runs it is not: an XPCS Run is a DAQ-owned high-rate frame stream (begin/end a per-frame burst correlated downstream into g2), which CORA's poll-to-Done acquisition bodies (`collect` / `discrete` / `continuous`) cannot execute. 8-ID is the second beamline after LCLS-MFX to hit this, which promoted the event-stream axis to Stage 1 (design-locked, gate-review next; recorded in CORA's design memory). No spine code lands in this pass.

- **The remaining scattering Methods.** Whether small-angle scattering and six-circle diffraction enter CORA's catalog is an owner decision; their Practices render unlinked, pending (`TECH-1`).

- **Full asset-tree scenarios and vendor Models.** Beyond the diffractometer Assembly / Fixture scenario above, no `test_8id_*.py` registers the full 8-ID asset tree (the optics spine, the XPCS endstation), and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the 8-ID team to confirm before the model can be trusted.*

8-ID was reverse-engineered from the beamline's own Bluesky instrument repo ([BCDA-APS/8id-bits](https://github.com/BCDA-APS/8id-bits)), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from a config snapshot rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet), including the catalog graduation and the diffractometer Assembly). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | Are the two undulators canted feeding separate branches, and do the four stations (`8-ID-A/D/E/I`) run off one beam in series or split? | One root Unit Asset `8-ID` with one optics spine feeding the stations in series. | One-vs-many beam walks in the [descriptor](index.md). |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the 8id-bits config current and correct? | The handles in the descriptor are taken from the config and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals for the four hutches. | Four hutches exist with permit signals to be named. | The Enclosure permit signals. |

### Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The two undulators (downstream DSID, upstream USID): types, periods, and whether canted. | Two `InsertionDevice` Assets; periods unconfirmed. | The insertion-device specs. |
| MONO-1 | Blocks-go-live | The MN1 monochromator energy range and crystal. | One `Monochromator` Asset (8idaSoft:MN1); range unconfirmed. | The monochromator energy model. |
| MONO-2 | Nice-to-have | The in-line `idt_mono` (8idaSoft:MONO): is it a second monochromator or a different optic? | Not modelled in this cut. | Whether it becomes a second Asset. |
| OPT-1 | Nice-to-have | The two FMBO mirrors: coatings and the bender / piezo-pitch axis roles. | Two `Mirror` Assets with the config's axis maps; coatings unconfirmed. | The mirror specs. |
| OPT-2 | Nice-to-have | The slit internal axis maps (most slits carried only a base PV in the config). | `Slit` Assets with base PVs; per-blade axes partial. | The slit axis maps. |
| OPT-3 | Blocks-go-live | The two CRL transfocators (rl1, rl2): lens material and the per-lens actuator roles (ten lenses each). | Two `Transfocator` Assets; x/y/pitch/yaw mapped, the ten lens actuators summarized. | The transfocator spec. |

### Diffractometer

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-build | The six-circle Huber geometry: confirm the circle roles (mu, eta, chi, phi, nu, delta) and which is sample versus detector arm. | A six-circle diffractometer modelled as a plain device with the config's axis map; this confirms the `Assembly(Diffractometer)` slot shape. | The circle geometry and the Assembly slots (see [Model](#deliberately-not-here-yet)). |
| DIFF-2 | Blocks-go-live | The reciprocal-space coordination: is hklpy2 driving an (h, k, l, energy) pseudo-axis over this geometry? | A `PseudoAxis` Asset (psic) is modelled for the reciprocal-space layer. | The pseudo-axis model. |

### Sample environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TEMP-1 | Nice-to-have | The LakeShore 336 controllers and the Quantum Northwest holders: sensor channels and the sample stages they regulate. | `TemperatureController` Assets at 8-ID-E and 8-ID-I. | The temperature-controller model. |
| SAMPLE-1 | Nice-to-have | The rheometer shear-cell: the six axes and the shear modes it supports. | One `Rheometer` Asset (loose Family) with a six-axis map. | The rheometer model. |
| SAMPLE-2 | Nice-to-have | The UR5 robotic sample changer (RobocartUR5): is it CORA-driven, and what is its sample-exchange model? | Deferred; not modelled (CORA has no sample-changer shape). | The sample-changer model. |

### Detector and XPCS

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The three area detectors (Eiger 4M, Lambda 2M, Rigaku 3M): models, sensors, and frame rates. | Three `Camera` Assets; models unconfirmed. | The detector Model bindings. |
| BPM-1 | Nice-to-have | The Sydor beam-position monitor and the four TetrAMM channels: which are position monitors versus intensity (I0) normalizers? | Bound to the graduated catalog `PositionMonitor` Family presenting the Sensor Role. | The monitor classification. |
| XPCS-1 | Nice-to-have | The fast shutter timing and its role in the XPCS exposure sequence. | One `Shutter` Asset (8ideSoft:fastshutter). | The fast-shutter model. |
| XPCS-2 | Nice-to-have | The flight-path geometry (length, swing) and the beam-stop relationship. | One `FlightPath` Asset (loose Family) plus a `BeamStop`. | The flight-path model. |
| XPCS-3 | Nice-to-have | The softGlue FPGA timing graph (8idMZ1): the signal routing for detector gating. | One `TimingController` Asset; the signal graph is not modelled. | The timing model. |

### Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | Nice-to-have | The vacuum and process-gas supplies the flight path and sample environments draw on. | Photon beam, cooling water, and vacuum carried in the descriptor. | The Supply records. |
