# Notes

## Techniques

*What the modelled part of P07 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P07's diffraction and high-field techniques earn no catalog Method today, so the Methods below render unlinked and are carried pending until a technique enters scope (`TECH-1`).

### High-energy materials-science diffraction

P07 uses a high-energy monochromatic beam to study engineering materials (bulk diffraction, residual stress, texture, in-situ deformation), reading the diffraction on the [four-circle diffractometer](sample.md) and the [Pilatus / PerkinElmer detectors](detector.md).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| High-energy diffraction | `diffraction` | bulk / engineering diffraction on the four-circle diffractometer + area detectors; reuses the `diffraction` slug, a further consumer (`TECH-1`) |

### High-field materials science

P07's EH2 endstation carries a 17 T high-field magnet for studies under applied magnetic field.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| High-field magnetic scattering | `magnetic_scattering` | scattering / diffraction in the 17 T magnet; reuses the `magnetic_scattering` slug P09 / 4-ID share, a further consumer (`TECH-1`) |

### A high-energy materials beamline on familiar vocabulary

P07 is the fleet's high-energy materials-science beamline. Its techniques reuse the `diffraction` and `magnetic_scattering` slugs already carried across the fleet, so none forces a new Method now. The instrument anatomy reuses existing Families: the multi-bounce mono binds `Monochromator`, the four-circle diffractometer `Goniometer`, the 17 T magnet the graduated catalog `Magnet` Family, the Linkam stage `TemperatureController`, the detectors `Camera`. The in-situ sample environment (the Linkam heating / cooling, the magnet) suits operando materials studies but coins no new Family.

### Not modelled yet

The concrete acquisition recipes (the diffraction / stress-mapping scans, the in-situ deformation / temperature ramps, the high-field scans) are not written yet; they join as the deployment approaches the point where CORA drives P07. Whether the diffraction Methods enter CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P07, and the trust shape that will gate it. First cut.*

Governance at P07 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P07 carries a governance wrinkle the other PETRA III beamlines do not: it is **jointly operated by Helmholtz-Zentrum Hereon (2/3) and DESY (1/3)** (`OPERATOR-1`). How that joint operation maps to CORA's Federation / Trust model (a single Site with a shared operator pool, or two Federation participants sharing a beamline) is a facility-governance question carried pending. For this first cut, P07 is modelled as a beamline on the PETRA III Site, with the Hereon stake noted on the [index](index.md) and as a question; the DESY / Hereon operator pool and safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance) (`GOV-1`).

P07 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P07, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals (across the optics and the two experiment hutches) and the interlock structure are carried pending and are not invented here (`PSS-1`). P07 also carries the hazard classes that come with its endstations: a high-energy beam, the 17 T superconducting magnet and its liquid-helium cryogen, and the Linkam furnace; those land with the instruments that bring them when the deployment firms up.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P07, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P07 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P07 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P07 new

P07 is an eleventh beamline at an existing Site, and the facility's high-energy materials-science beamline, jointly operated by Helmholtz-Zentrum Hereon (2/3) and DESY (1/3). Its distinguishing capabilities are high-energy diffraction for engineering materials and a 17 T high-field magnet endstation. At the modelling level it is a reuse-and-reinforce deployment, plus a governance note (the joint operation).

### No new families

P07 coins no new Family. The multi-bounce mono binds `Monochromator`; the four-circle diffractometer `Goniometer`; the hexapod `Hexapod`; the 17 T magnet the graduated catalog `Magnet` Family (a further consumer, after 4-ID / i10-1 / ID32 / P09); the Linkam stage `TemperatureController`; the slits `Slit`; the stages `LinearStage`; the detectors `Camera` / `EnergyDispersiveSpectrometer`. Nothing in the catalog changes.

### The control plane

P07 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, despite the Hereon / DESY joint operation (the beamline controls are the PETRA III stack). Its distinctive devices are the multi-bounce DCM (resolved axes), the 17 T magnet, and the Linkam stage. The handles are read from P07's public OnlineXML registry and carried confirm (`CTRL-1`); only the EH2 registry slice is public. The high-energy diffraction / high-field acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

### Deliberately not here yet

- **The joint-operation governance (`OPERATOR-1`).** The Hereon (2/3) + DESY (1/3) operation is a facility-governance fact carried as a question; how it maps to CORA's Federation / Trust model is pending.
- **The undulator parameters (`SRC-1`).** The gap / taper are read; the period is not exposed.
- **The optics detail (`OPT-1`).** The multi-bounce DCM crystal cut and the OH optics are carried confirm-pending.
- **The diffractometer structure (`DIFF-1`).** The four-circle count and the detector arm are pending; modelled as a `Goniometer` Asset.
- **The motor-bank axis roles (`GROUP-1`).** The `exp*` / `oh*` banks carry no per-axis role; grouped as stage Assets.
- **The magnet detail (`MAG-1`).** The 17 T field and control are pending; the Family is the graduated catalog `Magnet` (a further consumer, its per-Asset field detail pending).
- **The detector roster (`DET-1`).** The models and the EH2B detection are named, not fully bound.
- **The other hutches (`HOST-1`).** Only the EH2 slice is public; EH1 / EH3 / EH4 are noted, not modelled.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The diffraction Methods (`TECH-1`).** Whether they enter CORA's catalog is an owner decision; the Practices render unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p07_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P07 team to confirm before the model can be trusted.*

P07 was reverse-engineered from P07's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p07](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p07), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no crystal cuts, magnet field, or energy calibration. P07 is CORA's eleventh PETRA III beamline, jointly operated by Helmholtz-Zentrum Hereon and DESY. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch feeding an EH2 main and an EH2B secondary hutch, plus other hutches (EH1 / EH3 / EH4)? | A `p07-oh2` optics hutch and `p07-eh2` / `p07-eh2b` endstations, from the registry slice. | The Enclosure grouping. |
| OPERATOR-1 | Blocks-go-live | The Hereon (2/3) + DESY (1/3) joint operation: how does it map to CORA's Federation / Trust model? | A beamline on the PETRA III Site with a shared operator pool; the Hereon stake noted. | The operator / governance model. |
| HOST-1 | Nice-to-have | The other P07 hutches (EH1 / EH3 / EH4) are not in the public EH2 registry slice. Where are they? | Only EH2 / EH2B modelled; the others noted, not modelled. | The full hutch roster. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`exp*`, `oh*`). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; gap / taper read, period pending. | The source Asset detail. |
| OPT-1 | Blocks-go-live | The multi-bounce DCM crystal cut and energy range, and the OH optics. | A multi-bounce `Monochromator`; physical detail pending. | The optics modelling. |

### Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-build | The four-circle Eulerian diffractometer geometry and whether it composes a Diffractometer Assembly with a detector arm. | A `Goniometer` Asset (e4cv + two-theta), not the composed Diffractometer Assembly. | The diffractometer modelling. |
| MAG-1 | Blocks-go-live | The 17 T magnet field, cryogen, and control / ramp interface. | A 17 T superconducting `Magnet` (the graduated catalog Family, a further consumer); field and control pending. | The per-Asset magnet field / control detail. |
| SAMPLE-1 | Nice-to-have | The EH2 sample-hexapod geometry and the Linkam stage handles. | A `Hexapod` + a `TemperatureController`; geometry pending. | The sample modelling. |

### The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector roster per hutch, the Pilatus / PerkinElmer models (the `_old` controller suffix), and the EH2B detection. | `Camera` area detectors plus `EnergyDispersiveSpectrometer` MCAs; models pending. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P07 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY / Hereon personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent, the cooling / beam supplies, and the magnet liquid-helium supply. | Photon beam, cooling water, vacuum, and liquid helium. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY / Hereon operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do high-energy diffraction and high-field materials science enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `diffraction` / `magnetic_scattering` slugs; none coined. | The technique Capabilities. |
