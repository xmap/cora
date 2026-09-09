# Notes

## Techniques

*What the modelled part of ID28 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../esrf/index.md#the-techniques-adapted-here) is how a facility adapts it. ID28 runs momentum-resolved hard X-ray inelastic scattering, a Method not yet in CORA's catalog, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

### Momentum-resolved inelastic X-ray scattering

ID28 sets a meV-resolution incident energy with the high-resolution backscattering monochromator (scanned by tuning the crystal temperature, not a Bragg angle), places the multi-analyzer spectrometer arm at a scattering angle that selects the momentum transfer, and scans the incident energy against the fixed-angle analyzer crystals, counting the energy-analyzed scattered photons. The measurement is the intensity surface I(Q, energy-loss): how much energy the sample exchanges with the photon at a chosen momentum transfer, the signature of phonons and collective excitations.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Momentum-resolved inelastic X-ray scattering | `inelastic_x_ray_scattering` | the momentum transfer Q is set by the [spectrometer-arm two-theta](detector.md); the meV incident energy is scanned on the [backscattering monochromator](source.md) against the fixed-angle [multi-analyzer crystals](detector.md); the energy-analyzed signal is counted per analyzer; reuses the NSLS-II IXS Method, the second consumer; Method not yet in catalog |

It needs the [incident-energy chain](source.md) (the backscattering mono for the meV resolution), the [sample stage and its temperature environment](sample.md), and the [multi-analyzer spectrometer arm and its detectors](detector.md). The arm scattering angle sets the magnitude of the momentum transfer; the analyzer crystals fix the analyzed energy so the incident-energy scan reads out the energy loss.

### The same inelastic axis, in the hard X-ray regime

ID28 is the fleet's hard X-ray IXS instrument. The catalog already anticipates inelastic scattering (the SIX soft RIXS arm, the NSLS-II IXS beamline, the ID32 soft RIXS / XES arms), and ID28 reuses the `inelastic_x_ray_scattering` Method the NSLS-II IXS beamline left pending as the second consumer, deepening the case for that Capability without coining anything. The device that ties the inelastic beamlines together is the dispersive spectrometer arm: ID28's multi-analyzer crystal arm is a further consumer of the `SpectrometerArm` family, the sighting that reinforced the graduation earned at ID32, now landed as a catalog Family (see [Model](#a-further-spectrometerarm-consumer-held)).

### Not modelled yet

The concrete acquisition recipes (the per-Q energy scans, the analyzer alignment, the counting times, the analyzer-crystal array calibration) are not written yet; they join as the deployment approaches the point where CORA drives ID28. Whether momentum-resolved IXS enters CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at ID28, and the trust shape that will gate it. First cut.*

Governance at ID28 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [ESRF Site](../esrf/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

ID28 is CORA's second ESRF beamline, so the ESRF Site already exists (established with ID32): the operator pool and the safety-review structure are carried pending on the [ESRF Site](../esrf/index.md#safety-and-governance), shared across the facility's beamlines, until ESRF staff confirm them (`GOV-1`). ID28 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives ID28, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The ESRF personnel-safety permit signals and the photon and front-end shutters are absent from the BLISS Beacon config, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [ESRF Site](../esrf/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

ID28 adds the hazard classes that come with its endstation: a cryogenic sample environment (the 10 K displex cryostat and the cryogens it draws on) and a hard X-ray beam. Those land with the instruments that bring them, and an experiment Clearance would carry them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives ID28, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's ID28 content lives, why it coins no new family and adds a further SpectrometerArm consumer, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at ID28 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the incident-energy PseudoAxis, realized over the F700 temperature controller) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes ID28 new

ID28 is CORA's second ESRF beamline (after ID32), and it deepens the fleet's inelastic-scattering coverage with a distinct flavor: **momentum-resolved hard X-ray inelastic scattering (IXS)**. A high-resolution backscattering monochromator sets a meV-resolution incident energy, the sample scatters, and a multi-analyzer crystal spectrometer on a two-theta arm energy-analyzes the scattered beam in backscattering, mapping phonon and collective-excitation dispersions across momentum transfer. The fleet already has soft RIXS (SIX, ID32) and the NSLS-II IXS beamline; ID28 is the ESRF hard X-ray IXS instrument, reusing the pending `inelastic_x_ray_scattering` Method as the second consumer (`TECH-1`).

The second value is the Site re-test: ID28 exercises the ESRF Site and the BLISS / Tango / IcePAP control plane a second time, confirming the ID32 house-style modelling generalizes within the facility.

A modelling note worth surfacing: ID28's incident energy is **not** scanned by a Bragg angle. The high-resolution backscattering monochromator selects energy by the silicon crystal's lattice spacing, which is tuned by **temperature** (the ASL F700 controller carries a paired `monot` setpoint / `deltae` energy axis). CORA still models the incident energy as a `PseudoAxis`, but it is realized over the F700 temperature controller rather than a goniometer, so the `Monochromator` Asset and the `BeamEnergy` `PseudoAxis` are decoupled in a way an angle-scanned beamline's are not. This is the kind of mechanism the descriptor records (read from the config) so the model is intentional, not a mirror of an angular-mono assumption.

### A further SpectrometerArm consumer, held

ID28's IXS spectrometer is a `TwoThetaMultilayer` two-theta arm carrying an array of inclined analyzer crystals (`a2_inca` / `a3_inca` / `a4_inca`, each with chi / th), which binds the `SpectrometerArm` Family. This is a **further consumer** of the family that SIX coined and ID32 brought to a rule-of-three (SIX RIXS arm + ID32 RIXS arm + ID32 XES arm). ID28 is a further sighting that reinforced it, and the family has since **graduated** into the catalog (`RIXS-1`); ID28's arm binds it like any catalog Family, so this scaffold makes no catalog change of its own.

`SpectrometerArm` is the right home: it is an arm that **positions** an energy-dispersing element (here a crystal array, at SIX / ID32 a grating) and **carries** a detector, presenting the `Positioner` Role, which is why it never fit the point-Sensor families.

### No new families

Beyond the graduated `SpectrometerArm`, ID28 reuses the catalog throughout: the backscattering monochromator binds `Monochromator` (the meV backscattering reflection is a per-Asset setting); the HFM / VFM benders bind `Mirror`; the beam-defining slits bind `Slit`; the two in-vacuum undulators bind `InsertionDevice`; the incident energy is a `PseudoAxis` realized over the ASL F700 backscattering-crystal temperature controller (`monot` / `deltae`), not over a Bragg angle; the Basler / PCO detectors bind `Camera`; the sample-temperature environments (the 10 K displex LakeShore 340, the Oxford 700, the nanodac gas blower) bind `TemperatureController`; the oh2 Elettra beam-position monitor binds the graduated catalog `PositionMonitor` (presenting the `Sensor` Role, distinct from `FluxMonitor` by measuring beam position rather than flux); the front-end shutter binds `Shutter`; and the machine state binds the loose `StorageRing` via the BLISS MachInfo.

### Deliberately not here yet

- **The analyzer-crystal array identity (`IXS-1`).** The multi-analyzer arm carries an array of inclined analyzer crystals, each with its own chi / th and cylinder slit. The config provisions nine analyzer-slit positions (`a1h..a9h` / `a1v..a9v`) and `inca` controllers for `a2` / `a3` / `a4`; how many crystals are populated is `IXS-1`. The first cut carries the array as a per-Asset setting on the one `SpectrometerArm` Asset; promoting each crystal to a child Asset via `parent_id` is the nested-component-identity convention, itself at a rule-of-three gate (the IXS 10-ID diced-crystal `XTAL-1` question is the sibling), so ID28 flags it rather than asserting it.
- **The SpectrometerArm graduation (`RIXS-1`).** Landed; the family graduated into the catalog (SIX + ID32 RIXS/XES + ID28), so ID28's arm binds it directly. Only the per-Asset arm geometry stays pending.
- **The exact sample-stage and per-analyzer-detector handles (`SAMPLE-1`, `DET-1`).** Carried confirm-pending; the spectrometer arm, mono, mirrors, and sample cryostats carry their real BLISS handles.
- **The IXS Method.** Whether momentum-resolved IXS enters CORA's catalog is an owner decision; the Practice renders unlinked, pending, reusing the NSLS-II IXS slug (`TECH-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_id28_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the ID28 team to confirm before the model can be trusted.*

ID28 was reverse-engineered from the ESRF's open BLISS Beacon device database ([gitlab.esrf.fr/id28/beamline_configuration](https://gitlab.esrf.fr/id28/beamline_configuration), a git mirror of the live config), so the control handles on the [device pages](index.md) are the beamline's real BLISS / Tango / IcePAP addresses, read from the config rather than confirmed by staff (the ID32 house-style precedent). Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics zone (oh1 / oh2 / oh3) feeding the eh1 spectrometer endstation, or a different layout? | A shared `id28-optics` zone and the `id28-eh1` experiment hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The period and segment count of the two in-vacuum undulators (`u22gap` IVU22a, `u133gap` IVU13-3c). | Two in-vacuum undulators on the ESRF_Undulator device server; the names imply 22 mm and 13 mm periods, segment detail pending. | The source Asset detail. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The ESRF-EBS storage-ring state ID28 reads. | Observe-only machine state, a loose `StorageRing`; exact handles pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The backscattering crystal / reflection, the meV energy resolution, the energy-scan partition rule, and the premono (OH1) / postmono (OH2) roles ahead of the main mono (OH3). | A `Monochromator` on the PI E518 piezo (`pimth` / `pimchi`); the meV energy is scanned by the ASL F700 crystal-temperature axis (`monot` / `deltae`), not a Bragg angle; energy is a `PseudoAxis` over the F700. | The monochromator and incident-energy Assets. |
| OPT-1 | Nice-to-have | The HFM / VFM mirror coatings and bender mechanics. | Two-bender focusing mirrors bound to `Mirror`. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The blade-axis map of the primary, mono, and sample slits. | Beam-defining `Slit` Assets (BLISS `slits_ph` / `slits_pv` / `slits_mx` / `slits_sh` / `slits_sv`); each with horizontal / vertical gap and offset. | The slit Asset detail. |
| DIAG-1 | Nice-to-have | The oh2 Elettra beam-position monitor channel map: it binds the graduated catalog `PositionMonitor` (position-measuring), distinct from `FluxMonitor`; the per-Asset position-vs-flux channel detail is the residual. | The graduated catalog `PositionMonitor` (presenting `Sensor`); channel map pending. | The beam-position channel map. |

### The IXS spectrometer endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| RIXS-1 | Blocks-go-live | The multi-analyzer spectrometer arm (the `TwoThetaMultilayer` two-theta arm carrying the inclined analyzer crystals): the per-Asset arm geometry and axis map. | The arm binds the catalog `SpectrometerArm` Family (graduated across SIX + ID32 RIXS/XES + ID28); the per-Asset geometry stays pending. | The spectrometer-arm geometry; the family graduation is settled (see [Model](#a-further-spectrometerarm-consumer-held)). |
| IXS-1 | Blocks-go-live | The analyzer-crystal array: the config shows analyzer slits a1..a9 and inclined-analyzer (`inca`) controllers for a2 / a3 / a4 (each with chi / th); how many crystals are populated, and whether they are one arm Asset or identity-bearing child Assets. | One `SpectrometerArm` Asset carrying the crystal array as a per-Asset setting, not child Assets. | The analyzer-array modelling; the CORA structural choice is on [Model](#deliberately-not-here-yet). |
| SAMPLE-1 | Blocks-go-live | The IXS sample-positioning stage axes: which of the scattering-geometry axes (`sax` / `say` / `saz`, `th` / `sphi` / `chi`), the eh1_ss `iceid285` (`phi` / `omega` / `sz`), and the SmarAct fine stage make up the modelled stage. | A `LinearStage`; axis set pending. | The sample-stage modelling. |
| TEMP-1 | Nice-to-have | The sample-temperature environments (the 10 K displex LakeShore 340, the Oxford 700 cryostream, the nanodac gas blower) and which is the default. | `TemperatureController` Assets presenting the `Regulator` Role. | The temperature-control modelling. |
| DET-1 | Blocks-go-live | The per-analyzer IXS photon detectors and the Basler / PCO imaging cameras: how the `deta1..deta9` P201 counters and the `izero` / `ione` monitors map to the analyzer crystals. | The Basler and PCO bind `Camera`; the per-analyzer `deta1..deta9` counters and the `izero` / `ione` beam monitors are read from the config, the crystal map pending. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the BLISS / Tango / IcePAP handles read from the public Beacon config current and correct? | The handles in the descriptor are taken from the BLISS config and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The ESRF personnel-safety permit signals behind the shutters. The config exposes the front-end shutter (`fe`) and the vacuum beam shutters (`bsh1` / `bsh2` / `bsh3` on `id28/v-bsh/0..2`), but not the PSS permit leaves. | The shutters are modelled (`FrontEndShutter`, the `bsh*` leaves carried on the enclosures); the permit signals behind them are to be named, not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the displex cryostat cryogen supply. | Photon beam, cooling water, and vacuum on the optics and flight path. | The Supply observations. |
| GOV-1 | Nice-to-have | The ESRF operator pool and safety-review structure (site-level). | Carried pending on the ESRF Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Does momentum-resolved IXS enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `inelastic_x_ray_scattering` Method NSLS-II IXS left pending, the second consumer; none coined. | The IXS Capability. |
