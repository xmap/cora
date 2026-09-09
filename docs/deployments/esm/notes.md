# Notes

## Techniques

*What the modelled part of ESM is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md) is how a facility adapts it. ESM's technique is angle-resolved photoemission, a photoemission method new to CORA's catalog, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

### Angle-resolved photoemission

ARPES illuminates the sample with monochromatic soft X-rays and measures the kinetic energy and emission angle of the photoelectrons, mapping the electronic band structure. The measurement is the electron distribution recorded by the hemispherical analyzer over a pass-energy and lens-mode window, at a sample orientation set by the cryostat manipulator.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Angle-resolved photoemission | `angle_resolved_photoemission` | electron energy / angle spectra on the Scienta SES analyzer, at low temperature on the UHV manipulator; Method not yet in catalog |

It needs the [grating monochromator](source.md) (the incident energy), the [UHV cryostat manipulator](sample.md), and the [electron analyzer](detector.md). Polarization is set by the dual EPUs.

### Not modelled yet

The XPEEM/LEEM photoemission-microscopy branch is deferred (a future `ElectronMicroscope` Family; see [Model](#deliberately-not-here-yet)). The concrete acquisition recipes (Fermi-surface maps, energy-distribution curves, the analyzer sweep settings) are not written yet; they join as the deployment approaches the point where CORA drives ESM. See [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at ESM, and the trust shape that will gate it. First cut.*

Governance at ESM follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

ESM is not yet driven by CORA, so this shape is not yet instantiated. The profile collection exposes only coarse queue-server groups, not the human roster, so the NSLS-II operator and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md) (`GOV-1`).

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md), not on the beamline, and the beamline links up to them. ESM carries the soft X-ray hazard classes (ultra-high vacuum and the cryostat's cryogens at the ARPES endstation) that an experiment Clearance would carry; those land with the instruments that bring them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives ESM, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's ESM content lives, the `Manipulator` graduation and `ElectronAnalyzer` this deployment introduces, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at ESM |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What this deployment graduates

ESM both earns a new abstraction and consolidates two existing ones.

- **`ElectronAnalyzer` (new, since graduated).** The Scienta SES hemispherical electron energy analyzer is the ARPES detector: photon-in, electron-out, recording electron counts over a kinetic-energy by emission-angle window set by the pass energy and lens mode. No photon-detector Family covers an electron spectrometer, so ESM introduced a new `ElectronAnalyzer` Family (presents the Detector Role); it graduated into the catalog once SST (NSLS-II 7-ID HAXPES) earned the second Scienta SES (`ARPES-1`).
- **`Manipulator` (graduates).** ESM's LT six-axis UHV cryostat manipulator is the **second** UHV sample manipulator after SIX, earning the abstraction at the two-deployment threshold. `Manipulator` graduates into the catalog with this deployment, distinct from `Hexapod` (parallel-kinematic), `Goniometer` (crystal orientation), and a plain `LinearStage` / `RotaryStage`; axis count and cryo range are a per-Asset settings difference. SIX's references are swept loose to graduated in the same change. Its naming-r3 review (done at the SIX sighting, with the watch-item to confirm it is not a `Hexapod` / `Goniometer` synonym) is resolved: a serial UHV stack is a distinct mechanism.
- **`GratingMonochromator` (reuses).** ESM's PGM is the third soft X-ray plane-grating monochromator after SIX and CSX, so it binds the catalog Family rather than minting one.

### Deliberately not here yet

- **The XPEEM/LEEM branch (`21-ID-2`).** ESM's second endstation is a low-energy electron microscope (LEEM) / photoemission electron microscope (PEEM), an electron-optics imaging instrument distinct from the analyzer. It is deferred to a follow-on as a future loose `ElectronMicroscope` Family (`PEEM-1`); this cut models the ARPES branch (the 32-ID / SRX "one endstation first" precedent).

- **The sample-prep and load-lock transfer.** The sample-prep and analysis-chamber manipulators and the load-lock sample-transfer claw are present in the config but deferred; this cut models the main LT sample manipulator (`SAMPLE-1`).

- **The ARPES Method.** Whether angle-resolved photoemission enters CORA's catalog is an owner decision; the Practice renders unlinked, pending (`TECH-1`).

- **The simulated devices and full asset-tree scenarios.** No `test_esm_*.py` registers the ESM asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the ESM team to confirm before the model can be trusted.*

ESM was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/esm-arpes-profile-collection](https://github.com/NSLS2/esm-arpes-profile-collection)), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from the `startup/*.py` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet), including the `Manipulator` graduation and the deferred XPEEM branch). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The two EPUs (EPU57 on G1A, EPU105 on G1B): periods, the polarization (phase) model, and how the pair is coordinated. | Two `InsertionDevice` Assets; the phase axis carried as a setting. | The insertion-device specs. |
| ENC-1 | Blocks-go-live | Are the PV zones `XF:21IDA/B/C/D` separate shielded hutches or beam zones within fewer? | Four enclosures, one per zone. | The Enclosure grouping. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals for the hutches. | Permit leaves to be named; shutters are `XF:21ID-PPS{Sh:FE}` / `XF:21IDA-PPS{PSh}` / `XF:21IDC-PPS{PSh:1A/1B}`. | The Enclosure permit signals. |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the esm-arpes-profile-collection current and correct? | The handles in the descriptor are taken from the profile collection and carried confirm. | Verifying each Asset's control handle. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MONO-1 | Blocks-go-live | The PGM: the grating line densities, the c-value model, and the energy range. | A `GratingMonochromator` Asset (catalog Family) with energy / focus-const / grating-pitch / mirror-pitch / grating-translation axes. | The monochromator model. |
| OPT-1 | Nice-to-have | The mirrors (M1, M3 hexapod, M4A KB pair, M4B hexapod): coatings and axis roles. | `Mirror` Assets with the config's PV roots; coatings unconfirmed. | The mirror specs. |
| OPT-2 | Nice-to-have | The PGM slits, the M3 slit, and the A/B exit slits: the internal axis maps. | `Slit` Assets with base PVs; per-blade axes partial. | The slit axis maps. |
| DIAG-1 | Nice-to-have | The ESM Diagon (`XF:21IDA-OP{Diag:1`): is it a polarization diagnostic, and what does it report? | One `GenericProbe` Asset (placeholder classification). | The diagnostic classification. |

### ARPES endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ARPES-1 | Blocks-build | The Scienta SES analyzer (`XF21ID1-ES-SES`): the model, the lens modes, the pass-energy and kinetic-energy-window controls, and the acquisition modes. | An `ElectronAnalyzer` Asset (catalog Family) presenting the Detector Role. | The analyzer model and lens / pass-energy controls. |
| SAMPLE-1 | Blocks-go-live | The LT UHV cryostat manipulator: the live prefix (the config shows a provisional `{PRV` and a commented `{LT:1-Manip:EA5_1`), the six axes, the cryo range, and the sample-prep / load-lock chambers. | A `Manipulator` Asset (x/y/z + Rx/Ry/Rz) plus a `TemperatureController`. | The sample-environment model. |
| DET-1 | Nice-to-have | The QuadEM flux monitors (qem01-12): which are I0 versus drain-current, and where each sits. | Two representative `FluxMonitor` Assets; the full set summarized. | The flux-monitor map. |

### Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | Nice-to-have | The vacuum and cryogen supplies the UHV optics, the analyzer, and the cryostat draw on. | Photon beam, cooling water, and vacuum carried in the descriptor. | The Supply records. |
