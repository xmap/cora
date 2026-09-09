# Notes

## Techniques

*What the modelled part of CSX is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md) is how a facility adapts it. CSX's scattering legs reuse Methods already in the catalog's pending set, so they render unlinked and are carried pending until a technique enters scope (`TECH-1`).

### Resonant soft X-ray scattering

CSX tunes the soft X-ray energy to an absorption edge and measures the scattered intensity through the TARDIS diffractometer, resolving electronic and magnetic order in reciprocal space.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant soft X-ray scattering | `resonant_scattering` | RSXS on the TARDIS E6C; reuses the 4-ID `resonant_scattering` Method, in a soft X-ray regime (a Plan / settings difference) |
| Soft X-ray diffraction | `diffraction` | coherent soft X-ray diffraction through the TARDIS circles; reuses the 4-ID / 8-ID `diffraction` Method |

Both need the [grating monochromator](source.md) (the incident energy), the [TARDIS diffractometer](sample.md), and the [coherent detectors](detector.md). The arm and sample circles select the momentum transfer.

### Coherence and holography

CSX's defining quality is beam coherence: the FastCCD records coherent-scattering and holography patterns. This is carried as a beam-quality enabler and as settings on the scattering Methods above, not coined as its own Method; whether coherent soft X-ray scattering becomes a distinct catalog Method is an owner-scope decision (`TECH-1`).

### Not modelled yet

The concrete acquisition recipes (energy maps, reciprocal-space scans, coherent / holography exposures) are not written yet; they join as the deployment approaches the point where CORA drives CSX. See [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at CSX, and the trust shape that will gate it. First cut.*

Governance at CSX follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

CSX is not yet driven by CORA, so this shape is not yet instantiated. The profile collection exposes only coarse queue-server groups, not the human roster, so the NSLS-II operator and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md) (`GOV-1`).

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md), not on the beamline, and the beamline links up to them. CSX carries the soft X-ray hazard classes (ultra-high vacuum and the cryostat's cryogens at the in-vacuum endstation) that an experiment Clearance would carry; those land with the instruments that bring them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives CSX, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's CSX content lives, the `GratingMonochromator` graduation this deployment earns, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at CSX |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the TARDIS hkl `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What this deployment graduates

CSX is the **consolidation** deployment for soft X-ray. SIX (NSLS-II 2-ID) introduced `GratingMonochromator` as a loose family at n=1; CSX's VLS-PGM (`XF:23ID1-OP{Mono`, 200-2200 eV) is the **second** independent soft X-ray plane-grating monochromator, which earns the rule-of-three. So `GratingMonochromator` **graduates into the catalog** with this deployment: it becomes a catalog Family that both SIX and CSX bind, with the grating line density and energy range carried as a per-Asset settings difference (the `InsertionDevice` / `Monochromator` precedent), not a Family split. The SIX deployment's references are swept from loose to graduated in the same change. The catalog `Monochromator` (a crystal / multilayer Bragg optic) is deliberately not stretched to cover the grating mono; they are distinct optics. Its naming-r3 review is done.

CSX also **reinforces** an existing abstraction rather than adding one: its TARDIS endstation is an in-vacuum hkl E6C diffractometer whose circles bind the catalog `Goniometer` Family and the composed `Assembly(Diffractometer)`, a third hkl diffractometer after 4-ID and 8-ID (and the first in a soft X-ray, in-vacuum context). No new family is introduced.

### Deliberately not here yet

- **The fine piezo nanopositioner.** CSX carries a piezo nanopositioner for sample / lens fine-positioning; it is deferred (it would fold to `Hexapod` or stay a loose nanopositioner family, an owner call at the point it is modelled).

- **The reciprocal-space solver.** The TARDIS hkl pseudo-axis is modelled as a `PseudoAxis` device; the inverse-kinematics partition rule is `DIFF-2`, deferred (as on 4-ID / 8-ID).

- **The coherent / holography Method.** CSX's defining coherence (the FastCCD coherent-scattering and holography) is carried as a beam-quality enabler and settings on the existing scattering Methods, not coined as its own Method; whether coherent soft X-ray scattering enters the catalog is an owner decision (`TECH-1`).

- **The simulated devices and full asset-tree scenarios.** No `test_csx_*.py` registers the CSX asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the CSX team to confirm before the model can be trusted.*

CSX was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/csx-profile-collection](https://github.com/NSLS2/csx-profile-collection)), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from the `startup/csx1` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet), including the `GratingMonochromator` graduation). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | The 23-ID canted straight: do the two EPUs feed CSX (23-ID-1) plus a sibling branch, and is CSX one root Unit? | One root Unit `CSX` fed by the canted twin-EPU straight (the 32-ID precedent). | The source topology in the [descriptor](index.md). |
| ENC-1 | Blocks-go-live | Are the PV zones `XF:23IDA` / `XF:23ID1-OP` / `XF:23ID1-ES` separate shielded hutches or beam zones within fewer? | Two enclosures (front-end optics + the 23-ID-1 branch). | The Enclosure grouping. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the csx-profile-collection current and correct? | The handles in the descriptor are taken from the profile collection and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals for the hutches. | Permit leaves to be named; the front-end shutter is `XF:23ID1-PPS{Sh:FE}`. | The Enclosure permit signals. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The two EPUs (`EPU:1`, `EPU:2`): type, period, and the polarization (phase) model. | Two `InsertionDevice` Assets; the phase axis carried as a setting. | The insertion-device specs. |
| MONO-1 | Blocks-go-live | The VLS-PGM: the grating line densities, the c-value model, and the 200-2200 eV range. | A `GratingMonochromator` Asset (catalog Family) with energy / mirror-pitch / mirror-x / grating-pitch / grating-x axes. | The monochromator model. |
| OPT-1 | Nice-to-have | The mirrors (M1A front-end hexapod, M3A refocusing): coatings and axis roles. | `Mirror` Assets with the config's PV roots; coatings unconfirmed. | The mirror specs. |
| OPT-2 | Nice-to-have | The branch slits (`Slt:1` / `Slt:2` gap-center, `Slt:3` x/y): the internal axis maps. | `Slit` Assets with base PVs; per-blade axes partial. | The slit axis maps. |

### TARDIS endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-build | The TARDIS E6C geometry: confirm the circle roles (theta, delta, gamma, mu) and which is sample versus detector. | A 6-circle hkl E6C diffractometer binding the `Goniometer` Family + the `Assembly(Diffractometer)`. | The circle geometry and the Assembly binding. |
| DIFF-2 | Blocks-go-live | The reciprocal-space coordination: the hkl E6C inverse-kinematics over this geometry. | A `PseudoAxis` Asset for the reciprocal-space layer. | The pseudo-axis model. |
| SAMPLE-1 | Nice-to-have | The sample stage, the holography stage, and the cryostat: the axes, the cryo range, and the fine nanopositioner. | A `LinearStage` (sx / say / saz + holography) and a `TemperatureController`. | The sample-environment model. |

### Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The coherent detectors (FastCCD, AXIS), the scaler / MCS, and the diode: models, sensors, and channels. | `Camera` Assets, a `FluxMonitor` scaler, and a `GenericProbe` diode. | The detector models and channel map. |

### Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | Nice-to-have | The vacuum and cryogen supplies the UHV optics, the in-vacuum TARDIS, and the cryostat draw on. | Photon beam, cooling water, and vacuum carried in the descriptor. | The Supply records. |
