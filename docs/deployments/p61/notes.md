# Notes

## Techniques

*What the modelled part of P61 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P61's diffraction technique earns no catalog Method today, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

### High-energy white-beam / energy-dispersive diffraction

P61 uses the high-energy white beam from the damping wiggler for energy-dispersive diffraction (P61B engineering / materials studies) and Large Volume Press high-pressure / high-temperature in-situ studies (P61A), reading the [energy-dispersive detector](detector.md).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Energy-dispersive diffraction (white beam) | `energy_dispersive_diffraction` | high-energy white-beam energy-dispersive diffraction (P61B) and Large Volume Press in-situ studies (P61A); reuses the `energy_dispersive_diffraction` slug, a further consumer (`TECH-1`, `PRESS-1`) |

### A thin high-energy white-beam beamline

P61 is the fleet's high-energy white-beam wiggler beamline. Its technique reuses the `energy_dispersive_diffraction` slug already carried across the fleet, so it forces no new Method. The instrument anatomy reuses existing Families (`LinearStage`); the sparse registry slice means the model is deliberately thin, with the source, the Large Volume Press, and the detectors carried pending. The Large Volume Press (P61A), when exposed, would reuse the catalog `PressureCell` Family (graduated across 13-id and P02).

### Not modelled yet

The concrete acquisition recipes (the energy-dispersive diffraction scans, the LVP pressure / temperature ramps, the white-beam engineering measurements) are not written yet; they join as the deployment approaches the point where CORA drives P61. Whether the diffraction Method enters CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P61, and the trust shape that will gate it. First cut.*

Governance at P61 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P61 is CORA's seventeenth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P61 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P61, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals and the interlock structure are carried pending and are not invented here (`PSS-1`). P61 carries hazard classes specific to a high-energy white-beam / Large Volume Press beamline: the unmonochromated white beam (a stringent shielding / interlock case) and the LVP's high-pressure / high-temperature environment. Those land with the instruments that bring them when the deployment firms up; the press is modelled as a sample-environment `PressureCell` Asset when exposed, not a beam-steering device CORA drives.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P61, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P61 content lives, its place as the last OnlineXML-modelled PETRA III beamline, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P61 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P61 new

P61 is a seventeenth beamline at an existing Site, the facility's high-energy white-beam wiggler beamline (P61A Large Volume Press + P61B energy-dispersive diffraction). It is the **last PETRA III beamline with a public OnlineXML registry**, completing CORA's OnlineXML-driven coverage of the facility. At the modelling level it is a reuse-and-reinforce deployment, and a deliberately thin one given its sparse registry slice (one generic motor bank).

### No new families (a thin, honest model)

P61 coins no new Family. The motor bank binds `LinearStage`; the energy-dispersive detector is a pending `EnergyDispersiveSpectrometer` placeholder. Nothing in the catalog changes. The Large Volume Press (P61A), when exposed, would reuse the catalog `PressureCell` Family (graduated across 13-id and P02); it is carried pending (`PRESS-1`). The P61 registry slice exposes little beyond the grouped motor bank, so the source, the press, and the detectors are carried pending rather than invented, the model-what-the-source-supports posture as P11 / P21 / P23.

### The control plane

P61 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, with one quirk: P61 is the only PETRA III extras package on the `debian/stretch` branch (the others are `debian/jessie`), so its snapshot vintage may differ. The handles are read from P61's public OnlineXML registry and carried confirm (`CTRL-1`). The energy-dispersive diffraction acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

### Deliberately not here yet

- **The source (`SRC-1`).** P61 is a damping-wiggler beamline (`source: superconducting-wiggler`); the wiggler parameters are not exposed in this registry slice.
- **The Large Volume Press (`PRESS-1`).** P61A's press is not in the registry slice; would reuse the catalog `PressureCell` Family when exposed.
- **The motor-bank axis roles (`GROUP-1`).** The `eh_mot*` bank carries no per-axis role; grouped as one stage.
- **The detectors (`DET-1`).** The Ge energy-dispersive detector and any area detector are not in the registry slice; carried as a pending placeholder.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/stretch` (unusual for the set); some handles may lag the live Tango database.
- **The diffraction Method (`TECH-1`).** Whether it enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p61_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P61 team to confirm before the model can be trusted.*

P61 was reverse-engineered from P61's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p61](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p61), branch `debian/stretch`) and a verified research brief, not from a live connection. The P61 registry is thin: one generic motor bank, no source / press / detectors exposed. P61 is CORA's seventeenth PETRA III beamline, the high-energy white-beam wiggler beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a single experiment hutch (the registry exposes one host), and the P61A / P61B branch split? | A `p61-eh2` experiment hutch, from the OnlineXML `hasnp61eh2` host. | The Enclosure grouping. |
| GROUP-1 | Nice-to-have | The per-axis roles of the `eh_mot*` motor bank. | Grouped as one `LinearStage` stage carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The damping-wiggler source parameters (period, field), and whether the beam is white or monochromated per branch. | A damping wiggler delivering high-energy white beam; parameters pending. | The source Asset detail. |

### Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| PRESS-1 | Blocks-build | The Large Volume Press (P61A): its press / anvil control, and whether it should bind the catalog `PressureCell` Family. | A pending press; would reuse the catalog `PressureCell` (graduated across 13-id and P02) when exposed. | The press modelling. |

### The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The energy-dispersive (Ge solid-state) detector, and any area detectors, absent from this registry slice. | A pending `EnergyDispersiveSpectrometer` placeholder; the chain not invented. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P61 device, and whether the OnlineXML `debian/stretch` branch (unusual for the set) matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals, the white-beam shielding / interlock, and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does energy-dispersive diffraction enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `energy_dispersive_diffraction` slug; none coined. | The technique Capability. |
