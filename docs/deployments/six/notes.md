# Notes

## Techniques

*What the modelled part of SIX is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md) is how a facility adapts it. SIX's technique is resonant inelastic X-ray scattering, a soft X-ray scattering method new to CORA's imaging-heritage catalog, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

### Resonant inelastic X-ray scattering

RIXS tunes the incident soft X-ray energy to an absorption edge and measures the energy and momentum the sample exchanges with the scattered photon, so the measurement is a spectrum of the emitted light dispersed by the spectrometer arm onto the photon-counting camera.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant inelastic X-ray scattering | `resonant_inelastic_scattering` | the incident energy is set on the [grating monochromator](source.md); the emitted spectrum is dispersed by the [spectrometer arm](detector.md) and recorded on the photon-counting camera; Method not yet in catalog |

It needs the [grating monochromator](source.md) (the incident-energy and resolution chain, exit slit included), the [UHV cryostat sample](sample.md), and the [RIXS spectrometer arm and camera](detector.md). The arm scattering angle selects the momentum transfer.

### Not modelled yet

The concrete acquisition recipes (energy maps, emission-spectrum exposures, the arm-angle and resolution settings) are not written yet; they join as the deployment approaches the point where CORA drives SIX. Whether RIXS enters CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); soft X-ray is a new regime for the fleet (see [Open questions](#open-questions) for the world-facts to confirm first).

## Governance

*Who will act at SIX, and the trust shape that will gate it. First cut.*

Governance at SIX follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

SIX is not yet driven by CORA, so this shape is not yet instantiated. The profile collection exposes only coarse queue-server groups, not the human roster, so the NSLS-II operator and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md) (`GOV-1`).

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md), not on the beamline, and the beamline links up to them. SIX adds hazard classes the hard X-ray fleet does not carry: ultra-high vacuum and the cryostat's cryogens at the sample environment, which an experiment Clearance would carry; those land with the instruments that bring them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives SIX, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's SIX content lives, the loose families this first soft X-ray deployment introduced and has since graduated, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at SIX |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### New loose families

SIX is CORA's first soft X-ray beamline, a new optics, detector, and sample-environment regime. It introduced three device classes no hard X-ray catalog Family covered. All three have since **graduated**: `GratingMonochromator` became a catalog Family once CSX (NSLS-II 23-ID) earned the soft X-ray PGM, `Manipulator` once ESM (NSLS-II 21-ID) earned the UHV sample manipulator, and `SpectrometerArm` once ESRF ID32 (the RIXS and XES arms) and ID28 (the multi-analyzer arm) earned the dispersive spectrometer arm SIX coined (the Monochromator, SampleManipulator, and RIXSSpectrometer here bind them).

| Family | Presents | What it is | Status |
| --- | --- | --- | --- |
| `GratingMonochromator` | Positioner | the soft X-ray plane-grating monochromator (PGM): premirror at a fixed-focus c-value plus an interchangeable grating, no Bragg crystal | graduated (SIX + CSX, `MONO-1`) |
| `SpectrometerArm` | Positioner | the meters-long energy-dispersive RIXS arm (bridge truss + optics chamber + detector chamber) | graduated (SIX + ID32 RIXS/XES + ID28) |
| `Manipulator` | Positioner | the UHV cryostat sample manipulator (x/y/z/theta) | graduated (SIX + ESM, `SAMPLE-1`) |

The catalog `Monochromator` is deliberately not stretched to cover the PGM: its note describes a crystal / multilayer Bragg monochromator, and a plane-grating mono has no Bragg crystal, selects energy by grating pitch and translation, and takes its resolution from the exit slit, so `GratingMonochromator` is a distinct Family rather than a settings variant. Likewise `SpectrometerArm` is distinct from the catalog `EnergyDispersiveSpectrometer` (a point Sensor, not a multi-chamber dispersive arm); it presents the `Positioner` Role (an arm that positions a dispersing grating and carries a `Camera` at its focus).

### Deliberately not here yet

- **The RIXS-camera Family question.** The RIXS camera does on-detector single-photon centroiding and isolinear curvature correction, a photon-counting regime distinct from an integrating-frame area detector. It is modelled here as the catalog `Camera` with that behavior carried as a note; whether the photon-counting pipeline warrants its own Family is `RIXS-2`, deferred (a `Camera`-with-settings is the lower-risk first cut).

- **The EPU polarization DOF.** The elliptically-polarizing undulator adds a phase (polarization) axis beyond gap. It binds the catalog `InsertionDevice` with the polarization carried as a setting; whether the EPU phase warrants a distinct family is deferred until a second EPU beamline (`SRC-1`).

- **The legacy end-station PGM.** The profile collection carries a discarded second monochromator instance (`Mono:2` / `espgm`) and a dead `PGMjoe` class; only the live `Mono:1` PGM is modelled.

- **The RIXS Method.** Whether RIXS enters CORA's catalog is an owner decision; the Practice renders unlinked, pending (`TECH-1`).

- **The simulated devices and full asset-tree scenarios.** No `test_six_*.py` registers the SIX asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the SIX team to confirm before the model can be trusted.*

SIX was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/six-profile-collection](https://github.com/NSLS2/six-profile-collection)), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from the `startup/*.py` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet), including the new loose families). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | Does SIX share a canted straight with a sibling beamline, or run off its own undulator in series? | One root Unit Asset `SIX` on its own EPU straight. | The source topology in the [descriptor](index.md). |
| ENC-1 | Blocks-go-live | Are the PV zones `XF:02IDA/B/C/D` four separate shielded hutches or beam zones within fewer hutches? | Four enclosures, one per zone. | The Enclosure grouping. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the six-profile-collection current and correct? | The handles in the descriptor are taken from the profile collection and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals for the hutches. | Permit leaves to be named; the photon shutters are `XF:02ID-PPS{Sh:FE}` / `XF:02IDA-PPS{PSh}` / `XF:02IDB-PPS{PSh}`. | The Enclosure permit signals. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The EPU (`SR:C02-ID:G1A{EPU:1}`): type, period, and the polarization (phase) model. | One `InsertionDevice` Asset; the phase axis carried as a setting. | The insertion-device spec. |
| MONO-1 | Blocks-build | The plane-grating monochromator: energy range, the three grating line densities (500 / 1200 / 1800 l/mm), and the c-value (cff) model. | A `GratingMonochromator` Asset (catalog Family) with energy / cff / grating-pitch / premirror-pitch / grating-translation axes. | The monochromator energy and grating model. |
| OPT-1 | Nice-to-have | The mirrors (M1, M3, M4, M5, M6): coatings, stripes, and the hexapod / bender axis roles. | `Mirror` Assets with the config's PV roots; coatings unconfirmed. | The mirror specs. |
| OPT-2 | Nice-to-have | The baffle slits, the exit slit, and the M5 mask: the internal axis maps. | `Slit` / `Aperture` Assets with base PVs; per-blade axes partial. | The slit and aperture axis maps. |

### RIXS endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| RIXS-1 | Blocks-build | The spectrometer-arm geometry: the bridge truss (`BT:1`), the in-arm optics chamber (`3AA:1`), and the detector chamber (`DC:1`): which axis is the arm scattering angle, the dispersion, and the detector distance, and how the arm pivots about the sample chamber. | One `SpectrometerArm` Asset (catalog Family, graduated) with the three chambers' axes; the sample chamber as the pivot. | The spectrometer geometry and whether it composes into an Assembly. |
| RIXS-2 | Nice-to-have | The RIXS camera (`XF:02ID1-ES{RIXSCam}`): the sensor, the photon-counting / centroiding pipeline, and the curvature correction. | One `Camera` Asset; the centroiding behavior carried as a note. | The detector model and Family decision. |
| DET-1 | Nice-to-have | The counting scaler, the Femto electrometer, and the camera readout: which channels are I0 versus signal. | `FluxMonitor` Assets plus the `Camera`. | The detector channel map. |
| DIAG-1 | Nice-to-have | The DIAGON diagnostic (`XF:02IDA-OP{Diag:1`): is it a polarization diagnostic, and what does it report? | One `GenericProbe` Asset (placeholder classification). | The diagnostic classification and Family. |

### Sample environment and supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The UHV cryostat manipulator (`SC:1-Cryo:S1_B`) and the Lakeshore controller: the cryo temperature range, the base pressure, and any load-lock / sample-transfer mechanism. | A `Manipulator` Asset (catalog Family, x/y/z/theta) plus a `TemperatureController`. | The sample-environment model. |
| SUP-1 | Nice-to-have | The vacuum and cryogen supplies the UHV optics, the spectrometer arm, and the cryostat draw on. | Photon beam, cooling water, and vacuum carried in the descriptor. | The Supply records. |
